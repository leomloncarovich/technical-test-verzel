import os
import datetime as dt
from typing import List, Dict, Optional, Any
import httpx

MOCK = os.getenv("MOCK_EXTERNALS", "true").lower() == "true"
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

CAL_BASE = "https://api.cal.com"
CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_USERNAME = os.getenv("CAL_USERNAME")                 # ex: "leo-mosca-loncarovich"
CAL_EVENT_TYPE_SLUG = os.getenv("CAL_EVENT_TYPE_SLUG")   # ex: "30min"
CAL_EVENT_TYPE_ID = os.getenv("CAL_EVENT_TYPE_ID")       # ex: "3830730"
# Mantemos CAL_API_VERSION para slots/availability; bookings sempre usarão 2024-08-13
CAL_API_VERSION = os.getenv("CAL_API_VERSION", "2024-09-04")

# ---------- Helpers ----------
def _iso(d: dt.datetime) -> str:
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.isoformat()

def _tomorrow_range_local(start_h=9, end_h=18, tz=dt.timezone.utc) -> tuple[dt.datetime, dt.datetime]:
    now = dt.datetime.now(tz)
    tomorrow = (now + dt.timedelta(days=1)).date()
    start = dt.datetime.combine(tomorrow, dt.time(hour=start_h), tzinfo=tz)
    end = dt.datetime.combine(tomorrow, dt.time(hour=end_h), tzinfo=tz)
    return start, end

def _headers(required_version: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {CAL_API_KEY}",
        "Content-Type": "application/json",
        "cal-api-version": required_version,
    }

# ---------- MOCK ----------
def mock_slots(preferred_start: Optional[dt.datetime], preferred_end: Optional[dt.datetime]) -> List[Dict]:
    now = dt.datetime.now(dt.timezone.utc)
    base_date = (preferred_start.date() if preferred_start else (now + dt.timedelta(days=1)).date())
    if preferred_start and preferred_start < now:
        base_date = (now + dt.timedelta(days=1)).date()
    base = dt.datetime.combine(base_date, dt.time(12, 0, 0), tzinfo=dt.timezone.utc)  # 12:00Z ≈ 09:00 BRT
    raw = []
    for i in range(16):  # 09:00–16:30 BRT em passos de 30min
        s = base + dt.timedelta(minutes=30 * i)
        e = s + dt.timedelta(minutes=30)
        raw.append({"id": f"mock-{int(s.timestamp())}", "start": _iso(s), "end": _iso(e)})

    if preferred_start and preferred_end:
        filtered = []
        for r in raw:
            slot_start = dt.datetime.fromisoformat(r["start"].replace("Z", "+00:00"))
            if preferred_start <= slot_start <= preferred_end:
                filtered.append(r)
        if filtered:
            return filtered[:16]
        return [r for r in raw if dt.datetime.fromisoformat(r["start"].replace("Z", "+00:00")).date() == base_date][:16]

    return raw[:16]

def mock_schedule(slot_id: str) -> Dict:
    ts = slot_id.split("-")[-1]
    try:
        start = dt.datetime.utcfromtimestamp(int(ts)).replace(tzinfo=dt.timezone.utc)
    except Exception:
        start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1, hours=12)
    return {
        "meetingLink": f"https://meet.example/{slot_id}",
        "meetingDatetime": _iso(start),
        "bookingId": f"mock-bk-{int(start.timestamp())}"
    }

# ---------- Cal.com ----------
def get_slots(preferred_start: Optional[dt.datetime], preferred_end: Optional[dt.datetime]) -> List[Dict]:
    if MOCK:
        return mock_slots(preferred_start, preferred_end)

    if not (CAL_API_KEY and CAL_USERNAME and CAL_EVENT_TYPE_SLUG):
        return mock_slots(preferred_start, preferred_end)

    if not (preferred_start and preferred_end):
        preferred_start, preferred_end = _tomorrow_range_local(9, 18, tz=dt.timezone.utc)

    # Cal.com espera timezone IANA válido (ex: "America/Sao_Paulo" ou "UTC")
    # Garante que não está vindo com ":" ou outros caracteres inválidos
    timezone_value = TIMEZONE.strip() if TIMEZONE else "UTC"
    if timezone_value.startswith(":"):
        timezone_value = timezone_value[1:]  # Remove ":" se presente
    if not timezone_value or timezone_value == ":":
        timezone_value = "UTC"
    
    params = {
        "eventTypeSlug": CAL_EVENT_TYPE_SLUG,
        "username": CAL_USERNAME,
        "start": preferred_start.date().isoformat(),
        "end": preferred_end.date().isoformat(),
        "timeZone": timezone_value,
        "format": "range",
    }

    # slots usam 2024-09-04
    url = f"{CAL_BASE}/v2/slots"
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.get(url, headers=_headers("2024-09-04"), params=params)
            if r.status_code != 200:
                r.raise_for_status()
            r.raise_for_status()
            data = r.json()

        days = (data.get("data") or {})
        out: List[Dict] = []
        for _, slots_list in days.items():
            if not isinstance(slots_list, list):
                continue
            for ts in slots_list:
                s = ts.get("start") if isinstance(ts, dict) else None
                e = ts.get("end") if isinstance(ts, dict) else None
                if s:
                    out.append({"id": f"cal-{len(out)}-{s}", "start": s, "end": e or s})
        return out if out else mock_slots(preferred_start, preferred_end)

    except Exception:
        return mock_slots(preferred_start, preferred_end)

def _ensure_utc_z(iso_str: Optional[str]) -> Optional[str]:
    if not iso_str:
        return None
    # normaliza para terminar com Z
    s = iso_str
    if s.endswith("Z"):
        return s
    try:
        s = s.replace("Z", "+00:00")
        if "+" in s or "-" in s[-6:]:
            dt_obj = dt.datetime.fromisoformat(s)
        else:
            dt_obj = dt.datetime.fromisoformat(s + "+00:00")
        return dt_obj.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return iso_str  # deixa como veio

def cancel_booking(booking_id: str, reason: Optional[str] = None) -> Dict:
    """
    Cancela a reserva no Cal.com (ou faz mock se MOCK/sem API key).
    Usa cal-api-version 2024-08-13.
    """
    if MOCK or not CAL_API_KEY:
        return {"status": "canceled", "mock": True}

    url = f"{CAL_BASE}/v2/bookings/{booking_id}/cancel"
    headers = _headers("2024-08-13")
    body = {"reason": reason} if reason else {}

    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(url, headers=headers, json=body)
            if r.status_code not in (200, 204, 202):
                r.raise_for_status()
            r.raise_for_status()
            return r.json() if r.text else {"status": "ok"}
    except Exception as e:
        raise RuntimeError(f"Erro ao cancelar no Cal.com: {type(e).__name__}: {e}")

def schedule_slot(
    slot_id: str,
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,   # será ignorado com 2024-08-13
    attendee_name: Optional[str] = None,
    attendee_email: Optional[str] = None,
) -> Dict:
    if MOCK:
        return mock_schedule(slot_id)

    if not CAL_API_KEY:
        return mock_schedule(slot_id)

    headers = _headers("2024-08-13")  # bookings exigem esta versão

    start_utc = _ensure_utc_z(start_iso)
    if not start_utc:
        return mock_schedule(slot_id)

    # Cal.com espera timezone IANA válido (ex: "America/Sao_Paulo" ou "UTC")
    # Garante que não está vindo com ":" ou outros caracteres inválidos
    timezone_value = TIMEZONE.strip() if TIMEZONE else "UTC"
    if timezone_value.startswith(":"):
        timezone_value = timezone_value[1:]  # Remove ":" se presente
    if not timezone_value or timezone_value == ":":
        timezone_value = "UTC"

    body: Dict[str, Any] = {
        "start": start_utc,   # apenas start; NÃO enviar 'end'
        "attendee": {
            "name": attendee_name or "Convidado",
            "email": attendee_email or "lead@example.com",
            "timeZone": timezone_value,
            "language": "pt-BR",
        },
        "metadata": {"source": "ai-sdr"},
    }

    if CAL_EVENT_TYPE_ID:
        try:
            body["eventTypeId"] = int(CAL_EVENT_TYPE_ID)
        except ValueError:
            body["eventTypeSlug"] = CAL_EVENT_TYPE_SLUG
            body["username"] = CAL_USERNAME
    else:
        body["eventTypeSlug"] = CAL_EVENT_TYPE_SLUG
        body["username"] = CAL_USERNAME

    url = f"{CAL_BASE}/v2/bookings"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(url, headers=headers, json=body)
            if r.status_code not in (200, 201):
                r.raise_for_status()
            r.raise_for_status()
            data = r.json()

        payload = data.get("data") or data
        booking = payload.get("booking") or payload

        link = (
            booking.get("meetingUrl")
            or booking.get("hangoutLink")
            or booking.get("locationUrl")
            or booking.get("location")
            or "https://meeting.link"
        )
        start = booking.get("start") or start_utc
        booking_id = booking.get("id") or booking.get("uid") or booking.get("bookingId")

        return {
            "meetingLink": link,
            "meetingDatetime": start,
            "bookingId": booking_id,
        }

    except Exception:
        return mock_schedule(slot_id)
