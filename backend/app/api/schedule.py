from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from dateutil import parser as dtparser  # pip install python-dateutil
from sqlmodel import select
import httpx
import os

from app.core.calendar import get_slots, schedule_slot, cancel_booking
from app.models.db import get_session, Meeting, get_lead_by_session

router = APIRouter()

class ScheduleIn(BaseModel):
    slotId: str
    sessionId: str
    startIso: Optional[str] = None
    endIso: Optional[str] = None
    attendeeName: Optional[str] = None
    attendeeEmail: Optional[str] = None

class CancelIn(BaseModel):
    meetingId: Optional[int] = None
    bookingId: Optional[str] = None
    reason: Optional[str] = None

def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = dtparser.isoparse(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None

@router.get("/slots")
def slots(
    sessionId: str = Query(...),
    rangeStart: Optional[str] = Query(None),
    rangeEnd: Optional[str] = Query(None),
):
    start_dt = _parse_iso(rangeStart)
    end_dt = _parse_iso(rangeEnd)
    return {"slots": get_slots(start_dt, end_dt)}

@router.post("/schedule")
def schedule(body: ScheduleIn):
    with get_session() as db:
        # Busca o lead para usar nome e email se não foram fornecidos
        lead = get_lead_by_session(db, body.sessionId)
        attendee_name = body.attendeeName or (lead.name or "Convidado")
        attendee_email = body.attendeeEmail or lead.email

        if not attendee_email:
            attendee_email = f"lead-{body.sessionId[:8]}@example.com"
            print(f"[SCHEDULE] ⚠️ Email do lead não encontrado, usando: {attendee_email}")
        else:
            print(f"[SCHEDULE] Usando email do lead: {attendee_email}, nome: {attendee_name}")

        result = schedule_slot(
            body.slotId,
            start_iso=body.startIso,
            end_iso=body.endIso,
            attendee_name=attendee_name,
            attendee_email=attendee_email,
        )

        meeting = Meeting(
            session_id=body.sessionId,
            link=result["meetingLink"],
            datetime_iso=result["meetingDatetime"],
            booking_id=result.get("bookingId"),
        )
        db.add(meeting)
        db.commit()
        
        # Atualiza card no Pipefy se sessionId for um card_id do Pipefy
        # (assumimos que se sessionId é numérico e grande, pode ser um card_id)
        try:
            # Parse da data/hora do meeting
            meeting_dt = _parse_iso(result["meetingDatetime"])
            if meeting_dt:
                # Converte para timezone local (BRT) para exibição
                from zoneinfo import ZoneInfo
                BRT = ZoneInfo("America/Sao_Paulo")
                meeting_brt = meeting_dt.astimezone(BRT)
                
                meeting_date = meeting_brt.strftime("%Y-%m-%d")
                meeting_time = meeting_brt.strftime("%H:%M")
                
                # Chama endpoint interno para atualizar Pipefy
                # Faz de forma assíncrona para não bloquear a resposta
                try:
                    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
                    with httpx.Client(timeout=5.0) as client:
                        update_payload = {
                            "sessionId": body.sessionId,
                            "date": meeting_date,
                            "time": meeting_time,
                            "meetLink": result["meetingLink"],
                        }
                        # Faz chamada não-bloqueante (fire and forget)
                        # Em produção, considere usar background tasks do FastAPI
                        try:
                            client.post(
                                f"{base_url}/api/pipefy/updateBooking",
                                json=update_payload,
                                timeout=5.0
                            )
                            print(f"[SCHEDULE] ✅ Pipefy update iniciado para card {body.sessionId}")
                        except Exception as e:
                            # Não falha o agendamento se o Pipefy falhar
                            print(f"[SCHEDULE] ⚠️ Erro ao atualizar Pipefy (não crítico): {e}")
                except Exception as e:
                    print(f"[SCHEDULE] ⚠️ Erro ao preparar update do Pipefy: {e}")
        except Exception as e:
            print(f"[SCHEDULE] ⚠️ Erro ao processar data para Pipefy: {e}")
    
    return result

@router.post("/cancel")
def cancel(body: CancelIn):
    if not body.meetingId and not body.bookingId:
        raise HTTPException(status_code=400, detail="Informe meetingId ou bookingId")

    with get_session() as db:
        meeting = None
        if body.meetingId:
            meeting = db.get(Meeting, body.meetingId)

        if meeting is None and body.bookingId:
            stmt = select(Meeting).where(Meeting.booking_id == body.bookingId)
            meeting = db.exec(stmt).first()

        if meeting is None:
            raise HTTPException(status_code=404, detail="Meeting não encontrado")

        # Idempotência
        if meeting.canceled_at is not None:
            return {
                "status": "already_canceled",
                "meetingId": meeting.id,
                "bookingId": meeting.booking_id,
                "canceledAt": meeting.canceled_at.isoformat() if meeting.canceled_at else None,
                "reason": meeting.cancel_reason,
            }

        # Cancela no Cal.com (se tiver booking_id)
        if meeting.booking_id:
            try:
                cal_res = cancel_booking(meeting.booking_id, reason=body.reason)
                print("[CANCEL] Cal.com OK:", cal_res)
            except Exception as e:
                # Se preferir bloquear, troque por:
                # raise HTTPException(status_code=502, detail=str(e))
                print("[CANCEL] ⚠️ Falha ao cancelar no Cal.com:", e)

        # Marca cancelamento local
        meeting.canceled_at = datetime.utcnow()
        meeting.cancel_reason = body.reason
        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        return {
            "status": "canceled",
            "meetingId": meeting.id,
            "bookingId": meeting.booking_id,
            "canceledAt": meeting.canceled_at.isoformat() if meeting.canceled_at else None,
            "reason": meeting.cancel_reason,
        }
