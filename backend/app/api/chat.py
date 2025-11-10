from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select
from typing import List, Optional, Tuple
import re
from datetime import datetime, timedelta, time, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # py<3.9
    from backports.zoneinfo import ZoneInfo  # type: ignore

from app.core import llm
from app.models.db import (
    get_session,
    Message,
    Lead,
    init_db,
    get_lead_by_session,
    merge_lead,
)
from app.core.calendar import get_slots
from app.core.pipefy import update_card_lead_fields, create_card, find_card_by_email, FIELD_NAMES, _ensure_field_ids_initialized
from app.core.config import settings
import os

router = APIRouter()

_db_initialized = False
def _ensure_db():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception as e:
            print(f"[CHAT] ⚠️ Erro ao inicializar DB (pode ser normal): {e}")

BRT = ZoneInfo("America/Sao_Paulo")
SESSION_TTL_HOURS = settings.SESSION_TTL_HOURS

class ChatIn(BaseModel):
    message: str
    sessionId: str

def load_history(db, session_id: str, limit: int = 20) -> List[dict]:
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.ts.asc())
    rows = db.exec(stmt).all()
    return [{"role": m.role, "content": m.content, "ts": m.ts.isoformat()} for m in rows][-limit:]

def is_session_expired(db, session_id: str) -> Tuple[bool, Optional[datetime]]:
    """
    Verifica se a sessão expirou baseado na última mensagem.
    Retorna (is_expired, last_activity) onde last_activity é o timestamp da última mensagem.
    """
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.ts.desc())
    last_message = db.exec(stmt).first()
    
    if not last_message:
        return False, None
    
    last_activity = last_message.ts
    now = datetime.utcnow()
    ttl = timedelta(hours=settings.SESSION_TTL_HOURS)
    
    is_expired = (now - last_activity) > ttl
    return is_expired, last_activity

def _to_brt(dt: datetime) -> datetime:
    return dt.astimezone(BRT)

def _brt_hour_from_iso(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return _to_brt(dt).hour

def _brt_minute_from_iso(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return _to_brt(dt).minute

def filter_slots_by_window(slots: List[dict], rs: datetime, re: datetime) -> List[dict]:
    """
    Mantém apenas slots cujo horário BRT esteja dentro de [rs, re).
    Considera hora:minuto (não apenas hora cheia).
    """
    start_brt = _to_brt(rs)
    end_brt   = _to_brt(re)
    out = []
    for s in slots:
        slot_start_str = s.get("start", "")
        if not slot_start_str:
            continue
        if slot_start_str.endswith("Z"):
            slot_start_str = slot_start_str[:-1] + "+00:00"
        try:
            dt_start = datetime.fromisoformat(slot_start_str).astimezone(BRT)
            if start_brt <= dt_start < end_brt:
                out.append(s)
        except Exception:
            pass
    return out

def clamp_after_hour(slots: List[dict], h_min: int) -> List[dict]:
    """Garante slots >= h_min em BRT (ex.: 'a partir das 15')."""
    out = []
    for s in slots:
        try:
            hour = _brt_hour_from_iso(s["start"])
            if hour >= h_min:
                out.append(s)
        except Exception:
            out.append(s)
    return out

def _is_pipefy_card_id(session_id: str) -> bool:
    """
    Verifica se sessionId parece ser um card_id do Pipefy.
    Card IDs do Pipefy são geralmente numéricos e longos.
    """
    if not session_id:
        return False
    return session_id.isdigit() and len(session_id) >= 6

def prioritize_slots(slots: List[dict], alvo_h: Optional[int]) -> List[dict]:
    """Ordena por distância à hora alvo (em BRT) se houver alvo."""
    if alvo_h is None or not slots:
        return slots
    return sorted(
        slots,
        key=lambda s: abs(_brt_hour_from_iso(s["start"]) - alvo_h) + (_brt_minute_from_iso(s["start"]) / 60.0)
    )

WEEKDAYS = {
    "segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6
}

def _today_brt() -> datetime:
    return datetime.now(BRT)

def _next_weekday(base_date, target_wd: int, include_today=False):
    cur_wd = base_date.weekday()
    delta = (target_wd - cur_wd) % 7
    if delta == 0 and not include_today:
        delta = 7
    return base_date + timedelta(days=delta)

def parse_date_pt(text: str) -> Tuple[datetime, bool]:
    """
    Retorna (data_base_BRT 00:00, menciona_amanha)
    Entende: hoje, amanhã, 'dia 10', '10/11', '10/11/2025', 'na sexta', 'próxima quarta'.
    """
    t = (text or "").lower()
    now = _today_brt()
    base = now.date()
    mentions_tomorrow = False

    if "amanha" in t:
        base = (base + timedelta(days=1))
        mentions_tomorrow = True
        return datetime.combine(base, time(0,0), tzinfo=BRT), mentions_tomorrow

    if "hoje" in t:
        return datetime.combine(base, time(0,0), tzinfo=BRT), mentions_tomorrow

    m = re.search(r"(pr[óo]xima?|na|no)\s+(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)", t)
    if m:
        wd = WEEKDAYS[m.group(2)]
        nxt = _next_weekday(base, wd, include_today=("hoje" in t))
        return datetime.combine(nxt, time(0,0), tzinfo=BRT), mentions_tomorrow

    m = re.search(r"\bdia\s+(\d{1,2})\b", t)
    if m:
        d = int(m.group(1))
        month = now.month
        year = now.year
        try:
            return datetime(year, month, d, 0, 0, tzinfo=BRT), mentions_tomorrow
        except ValueError:
            pass

    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        d, mo, yr = int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else now.year
        if yr < 100:
            yr += 2000
        try:
            return datetime(yr, mo, d, 0, 0, tzinfo=BRT), mentions_tomorrow
        except ValueError:
            pass

    return datetime.combine(base, time(0,0), tzinfo=BRT), mentions_tomorrow

def parse_time_prefs_pt(text: str) -> Tuple[Optional[int], Optional[int], Optional[int], str]:
    """
    Retorna (start_h, end_h, alvo_h, modo)
    modo: "range" | "after" | "around" | "period" | "none"
    Regras: entende manhã/tarde; 'a partir/após/depois de X'; 'X até Y';
            'próximo/perto/às X'; hora solta '15' como fallback.
    """
    t_raw = (text or "").lower()
    t = re.sub(r"\bdia\s+\d{1,2}\b", "", t_raw)
    t = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if any(k in t for k in ["manhã","manha","de manhã","de manha"]):
        return 8, 12, None, "period"
    if any(k in t for k in ["tarde","à tarde","a tarde","depois do almoço","mais tarde"]):
        return 13, 18, None, "period"

    m = re.search(r"(a partir|ap[óo]s|depois)\s+(?:d?[àa]s?\s*)?(\d{1,2})h?", t)
    if m:
        h = min(max(int(m.group(2)), 0), 23)
        return h, 20, h, "after"

    nums = re.findall(r"\b(\d{1,2})h?\b", t)
    if "até" in t and len(nums) >= 2:
        h1, h2 = int(nums[0]), int(nums[1])
        return min(h1, h2), max(h1, h2), (h1 + h2)//2, "range"

    m = re.search(r"(pr[óo]ximo|perto|[àa]s?)\s*(\d{1,2})h?", t)
    if m:
        h = min(max(int(m.group(2)), 0), 23)
        return max(8, h-2), min(20, h+2), h, "around"

    nums = re.findall(r"\b(\d{1,2})h?\b", t)
    if nums:
        h = min(max(int(nums[-1]), 0), 23)
        return max(8, h-2), min(20, h+2), h, "around"

    return None, None, None, "none"

def plan_windows(text: str) -> Tuple[datetime, datetime, Optional[int], str, List[Tuple[datetime,datetime]]]:
    """
    Constrói janelas (BRT→UTC) priorizadas:
    - data pedida (ou hoje) com preferências de hora
    - se zero slots e usuário não disse 'amanhã', tenta mesma janela +1 dia
    - fallback: dia inteiro da data base (ou de amanhã)
    Retorna: (startUTC, endUTC, alvo_h, modo, fallback_listUTC)
    """
    base_brt, said_tomorrow = parse_date_pt(text)
    sh, eh, alvo, modo = parse_time_prefs_pt(text)

    if sh is None and eh is None:
        sh, eh = (13, 18) if said_tomorrow else (9, 18)

    start_brt = datetime.combine(base_brt.date(), time(sh, 0, tzinfo=BRT))
    end_brt   = datetime.combine(base_brt.date(), time(eh, 0, tzinfo=BRT))
    start_utc = start_brt.astimezone(timezone.utc)
    end_utc   = end_brt.astimezone(timezone.utc)

    fallbacks: List[Tuple[datetime,datetime]] = []

    if not said_tomorrow:
        fs = (start_brt + timedelta(days=1)).astimezone(timezone.utc)
        fe = (end_brt + timedelta(days=1)).astimezone(timezone.utc)
        fallbacks.append((fs, fe))

    whole = base_brt.date() if said_tomorrow else (base_brt + timedelta(days=1)).date()
    ws = datetime.combine(whole, time(0,0), tzinfo=BRT).astimezone(timezone.utc)
    we = datetime.combine(whole, time(23,59,59), tzinfo=BRT).astimezone(timezone.utc)
    fallbacks.append((ws, we))

    return start_utc, end_utc, alvo, modo, fallbacks

@router.post("/chat")
def chat(body: ChatIn):
    _ensure_db()
    _ensure_field_ids_initialized()
    
    original_session_id = body.sessionId
    session_id = original_session_id
    
    with get_session() as temp_db:
        expired, last_activity = is_session_expired(temp_db, session_id)
        if expired:
            return {
                "reply": "Sua sessão expirou por inatividade. Por favor, recarregue a página para iniciar uma nova conversa.",
                "action": {"type": "SESSION_EXPIRED"},
                "sessionId": session_id,
            }
    
    old_lead_data = None
    existing_card_id = None
    
    try:
        with get_session() as temp_db:
            old_lead = get_lead_by_session(temp_db, original_session_id)
            if old_lead and (old_lead.name or old_lead.email or old_lead.company):
                old_lead_data = {
                    "name": old_lead.name,
                    "email": old_lead.email,
                    "company": old_lead.company,
                    "need": old_lead.need,
                }
            
            try:
                if old_lead_data and old_lead_data.get("name") and old_lead_data.get("email"):
                    stmt = select(Lead).where(
                        (Lead.name == old_lead_data.get("name")) &
                        (Lead.email == old_lead_data.get("email")) &
                        (Lead.session_id != original_session_id)
                    )
                    matching_lead = temp_db.exec(stmt).first()
                    if matching_lead and _is_pipefy_card_id(matching_lead.session_id):
                        existing_card_id = matching_lead.session_id
            except Exception:
                pass
    except Exception:
        pass
    
    if existing_card_id:
        session_id = existing_card_id
        body.sessionId = session_id
    
    with get_session() as db:
        try:
            db.add(Message(session_id=session_id, role="user", content=body.message))
            db.commit()

            lead = get_lead_by_session(db, session_id)
            
            if session_id != original_session_id and old_lead_data and not (lead.name and lead.email):
                merged_old = merge_lead(lead, old_lead_data)
                db.add(merged_old)
                db.commit()
                db.refresh(merged_old)
                lead = merged_old
            
            if lead.email and "@" in lead.email and not _is_pipefy_card_id(session_id):
                try:
                    pipe_id = os.getenv("PIPEFY_PIPE_ID", "306783445")
                    existing_card_id = find_card_by_email(pipe_id, lead.email)
                    
                    if existing_card_id:
                        lead.interest_confirmed = None
                        session_id = str(existing_card_id)
                        body.sessionId = session_id
                        lead.session_id = session_id
                        db.add(lead)
                        db.commit()
                        db.refresh(lead)
                except Exception:
                    pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
        
        history = load_history(db, session_id)
        if not history and session_id != original_session_id:
            old_history = load_history(db, original_session_id)
            if old_history:
                for msg in old_history:
                    msg_obj = Message(session_id=session_id, role=msg["role"], content=msg["content"])
                    db.add(msg_obj)
                db.commit()
                history = load_history(db, session_id)
        
        is_re_engagement = (
            _is_pipefy_card_id(session_id) and 
            session_id != original_session_id and
            lead.email and "@" in lead.email and
            lead.interest_confirmed is False
        )
        
        if is_re_engagement:
            lead.interest_confirmed = None
            db.add(lead)
            db.commit()
            db.refresh(lead)

        is_re_engagement_detected = (
            _is_pipefy_card_id(session_id) and 
            session_id != original_session_id
        )
        
        def build_state(slots=None):
            context_data = {"slots": slots} if slots else {}
            if is_re_engagement_detected:
                context_data["is_re_engagement"] = True
                context_data["re_engagement_note"] = "ATENÇÃO: Este lead estava 'Não Interessado' anteriormente, mas está re-engajando. IGNORE qualquer indicação de não interesse no histórico antigo e trate como uma nova oportunidade. Se o lead expressar interesse agora, defina interestConfirmed: true."
            
            return {
                "lead": {
                    "name": lead.name,
                    "email": lead.email,
                    "company": lead.company,
                    "need": lead.need,
                    "interestConfirmed": lead.interest_confirmed,
                },
                "context": context_data,
                "history": history,
            }

        resp = llm.respond(build_state(), body.message)
        lead_partial_from_llm = resp.get("leadPartial") or {}
        merged = merge_lead(lead, lead_partial_from_llm)
        
        if merged.email and "@" in merged.email and not _is_pipefy_card_id(session_id):
            try:
                pipe_id = os.getenv("PIPEFY_PIPE_ID", "306783445")
                existing_card_id = find_card_by_email(pipe_id, merged.email)
                
                if existing_card_id:
                    merged.interest_confirmed = None
                    session_id = str(existing_card_id)
                    body.sessionId = session_id
                    is_re_engagement_detected = True
            except Exception as e:
                pass
        
        db.add(merged)
        db.commit()
        db.refresh(merged)
        
        has_all_required_data = (
            merged.name and 
            merged.email and "@" in merged.email and 
            merged.company and 
            merged.need
        )
        
        if has_all_required_data and not _is_pipefy_card_id(session_id):
            try:
                pipe_id = os.getenv("PIPEFY_PIPE_ID", "306783445")
                existing_card_id = find_card_by_email(pipe_id, merged.email)
                
                if existing_card_id:
                    session_id = str(existing_card_id)
                    body.sessionId = session_id
                    merged.session_id = session_id
                    db.add(merged)
                    db.commit()
                    db.refresh(merged)
                else:
                    fields_to_use = {
                        FIELD_NAMES["nome_do_lead"]: merged.name,
                        FIELD_NAMES["email_do_lead"]: merged.email,
                        FIELD_NAMES["empresa_do_lead"]: merged.company,
                        FIELD_NAMES["necessidade_do_lead"]: merged.need,
                    }
                    
                    card_title = f"{merged.name.strip()} - {merged.email.strip()}"
                    result = create_card(
                        pipe_id=pipe_id,
                        title=card_title,
                        fields=fields_to_use,
                    )
                    
                    if result and isinstance(result, dict):
                        card = result.get("card")
                        if card and isinstance(card, dict):
                            new_card_id = card.get("id")
                            if new_card_id:
                                session_id = str(new_card_id)
                                body.sessionId = session_id
                                merged.session_id = session_id
                                db.add(merged)
                                db.commit()
                                db.refresh(merged)
            except Exception:
                pass
        
        if session_id != original_session_id and (merged.name or merged.email or merged.company):
            original_lead = get_lead_by_session(db, original_session_id)
            if not (original_lead.name and original_lead.email):
                original_lead.name = merged.name
                original_lead.email = merged.email
                original_lead.company = merged.company
                original_lead.need = merged.need
                original_lead.interest_confirmed = merged.interest_confirmed
                db.add(original_lead)
                db.commit()
        
        if _is_pipefy_card_id(session_id):
            has_data_to_sync = (
                (merged.name and merged.name != "Aguardando coleta...") or
                (merged.email and merged.email != "aguardando@coleta.com") or
                (merged.company and merged.company != "Aguardando coleta...") or
                (merged.need and merged.need != "Aguardando coleta...")
            )
            
            if has_data_to_sync:
                try:
                    name_to_sync = merged.name if (merged.name and merged.name != "Aguardando coleta...") else None
                    email_to_sync = merged.email if (merged.email and merged.email != "aguardando@coleta.com") else None
                    company_to_sync = merged.company if (merged.company and merged.company != "Aguardando coleta...") else None
                    need_to_sync = merged.need if (merged.need and merged.need != "Aguardando coleta...") else None
                    interest_confirmed = merged.interest_confirmed if merged.interest_confirmed is not None else None
                    
                    no_interest_reason = None
                    if interest_confirmed is False:
                        no_interest_reason = (
                            lead_partial_from_llm.get("noInterestReason") or
                            lead_partial_from_llm.get("motivo") or
                            lead_partial_from_llm.get("motivo_nao_interesse")
                        )
                        
                        if not no_interest_reason and need_to_sync:
                            no_interest_reason = need_to_sync
                        
                        if not no_interest_reason:
                            user_message_lower = body.message.lower()
                            if len(body.message.strip()) > 10 and not any(word in user_message_lower for word in ["oi", "olá", "bom dia", "boa tarde", "boa noite", "?"]):
                                no_interest_reason = body.message.strip()
                        
                        if not no_interest_reason:
                            no_interest_reason = "Não especificado pelo lead"
                    
                    if interest_confirmed is False and not no_interest_reason:
                        no_interest_reason = "Não especificado pelo lead"
                    
                    update_card_lead_fields(
                        card_id=session_id,
                        name=name_to_sync,
                        email=email_to_sync,
                        company=company_to_sync,
                        need=need_to_sync,
                        interest_confirmed=interest_confirmed,
                        no_interest_reason=no_interest_reason if interest_confirmed is False else None,
                    )
                except Exception:
                    pass

        want_slots = merged.interest_confirmed is True
        offered_slots = (resp.get("action") or {}).get("type") == "OFFER_SLOTS"

        if want_slots and not offered_slots:
            rs, re, alvo_h, modo, fallbacks = plan_windows(body.message)
            slots = get_slots(rs, re)
            slots = filter_slots_by_window(slots, rs, re)

            if modo == "after" and alvo_h is not None:
                slots = clamp_after_hour(slots, alvo_h)

            i = 0
            while not slots and i < len(fallbacks):
                fs, fe = fallbacks[i]
                slots = get_slots(fs, fe)
                slots = filter_slots_by_window(slots, fs, fe)
                if modo == "after" and alvo_h is not None:
                    slots = clamp_after_hour(slots, alvo_h)
                i += 1

            slots = prioritize_slots(slots, alvo_h)
            slots = slots[:5]

            if not slots:
                base_brt, _ = parse_date_pt(body.message)
                if base_brt.date() != _today_brt().date():
                    dia_inicio_utc = datetime.combine(base_brt.date(), time(0,0), tzinfo=BRT).astimezone(timezone.utc)
                    dia_fim_utc = datetime.combine(base_brt.date(), time(23,59,59), tzinfo=BRT).astimezone(timezone.utc)
                    alt_slots = get_slots(dia_inicio_utc, dia_fim_utc)
                    if alt_slots:
                        alt_slots = [s for s in alt_slots if _to_brt(datetime.fromisoformat(s["start"].replace("Z", "+00:00"))).date() == base_brt.date()]
                        if alt_slots:
                            alt_slots = sorted(alt_slots, key=lambda s: s.get("start", ""))[:5]
                            slots = alt_slots
                
                if not slots:
                    from datetime import timedelta
                    tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    week_later_utc = tomorrow_utc + timedelta(days=7)
                    alt_slots = get_slots(tomorrow_utc, week_later_utc)
                    if alt_slots:
                        alt_slots = sorted(alt_slots, key=lambda s: s.get("start", ""))[:5]
                        slots = alt_slots

            if not slots:
                resp["reply"] = "Desculpe, não encontrei horários disponíveis no período solicitado. Você teria alguma outra preferência de dia e horário?"
                resp["action"] = {"type": "ASK"}
            else:
                base_brt, _ = parse_date_pt(body.message)
                slots_date = None
                if slots:
                    first_slot_date = _to_brt(datetime.fromisoformat(slots[0]["start"].replace("Z", "+00:00"))).date()
                    slots_date = first_slot_date
                
                if modo == "after" and alvo_h is not None and slots_date == base_brt.date():
                    prompt = f"O usuário pediu horários após as {alvo_h}h do dia {base_brt.strftime('%d/%m')}, mas só temos disponibilidade em outros horários do mesmo dia. Ofereça estes horários explicando que são do dia solicitado mas em horários diferentes, e pergunte se algum deles funciona."
                else:
                    prompt = "Ofereça estes horários para o usuário, no mesmo idioma."
                
                resp = llm.respond(build_state(slots=slots), prompt)
                act = resp.get("action") or {}
                if not act.get("type"):
                    act["type"] = "OFFER_SLOTS"
                act["slots"] = slots
                reply_text = act.get("reply") or resp.get("reply") or "Perfeito! Esses horários funcionam pra você?"
                act["reply"] = reply_text
                resp["action"] = act
                if not resp.get("reply"):
                    resp["reply"] = reply_text

        reply = resp.get("action", {}).get("reply") or resp.get("reply") or "Certo."
        db.add(Message(session_id=session_id, role="assistant", content=reply))
        db.commit()
        
        if "sessionId" not in resp:
            resp["sessionId"] = session_id
        
        return resp
