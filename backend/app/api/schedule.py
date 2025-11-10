from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from dateutil import parser as dtparser  # pip install python-dateutil
from sqlmodel import select
import httpx
import os

from app.core.calendar import get_slots, schedule_slot, cancel_booking
from app.models.db import get_session, Meeting, get_lead_by_session, Lead, Message
from app.core.pipefy import find_card_by_title, find_card_by_email

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
        attendee_email = body.attendeeEmail or (lead.email if lead.email else None)

        if not attendee_email:
            raise HTTPException(
                status_code=400,
                detail="Email do lead não encontrado. Por favor, forneça um email válido."
            )

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
        # Primeiro, tenta encontrar o card_id do Pipefy se sessionId for um UUID
        pipefy_card_id = body.sessionId
        
        def _is_pipefy_card_id(session_id: str) -> bool:
            """Verifica se sessionId parece ser um card_id do Pipefy."""
            if not session_id:
                return False
            return session_id.isdigit() and len(session_id) >= 6
        
        if not _is_pipefy_card_id(pipefy_card_id):
            # Se não é um card_id, tenta encontrar o card_id correspondente
            try:
                pipe_id = os.getenv("PIPEFY_PIPE_ID", "306783445")
                found_card_id = None
                
                # PRIORIDADE 1: Busca no banco de dados por um lead com card_id que tenha o mesmo email
                # Isso é mais confiável porque o email é único
                if lead.email and "@" in lead.email:
                    stmt = select(Lead).where(
                        (Lead.email == lead.email) &
                        (Lead.session_id != body.sessionId)
                    )
                    matching_leads = db.exec(stmt).all()
                    for matching_lead in matching_leads:
                        if _is_pipefy_card_id(matching_lead.session_id):
                            found_card_id = matching_lead.session_id
                            break
                
                # PRIORIDADE 2: Se não encontrou no DB, busca no Pipefy por email (mais confiável que título)
                if not found_card_id and lead.email and "@" in lead.email:
                    found_card_id = find_card_by_email(pipe_id, lead.email)
                
                # PRIORIDADE 3: Se não encontrou por email, busca no Pipefy pelo título (UUID)
                if not found_card_id:
                    found_card_id = find_card_by_title(pipe_id, body.sessionId[:20])
                
                # PRIORIDADE 4: Busca no banco de dados por qualquer lead com card_id relacionado ao UUID
                # Verifica se há mensagens ou meetings com o UUID que possam indicar o card_id
                if not found_card_id:
                    # Busca mensagens com o UUID para encontrar o card_id relacionado
                    stmt = select(Message).where(Message.session_id == body.sessionId).limit(1)
                    message = db.exec(stmt).first()
                    if message:
                        # Se há mensagens, busca por leads que possam estar relacionados
                        # Busca por qualquer lead com card_id que tenha sido criado recentemente
                        stmt = select(Lead).where(
                            (Lead.session_id != body.sessionId) &
                            (Lead.email.isnot(None))
                        )
                        # Tenta encontrar um lead que possa estar relacionado
                        # (esta é uma busca menos precisa, mas pode ajudar)
                        pass  # Esta busca é muito ampla, vamos pular
                
                if found_card_id:
                    pipefy_card_id = found_card_id
                else:
                    return result
            except Exception:
                # Continua sem atualizar Pipefy se não conseguir encontrar o card_id
                pass
        
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
                
                # Atualiza Pipefy diretamente (sem chamada HTTP interna)
                try:
                    from app.core.pipefy import update_card_booking
                    update_card_booking(
                        card_id=pipefy_card_id,
                        meeting_date=meeting_date,
                        meeting_time=meeting_time,
                        meeting_location=result["meetingLink"],
                        phase_id=None,
                    )
                except Exception:
                    # Não falha o agendamento se o Pipefy falhar
                    pass
        except Exception:
            pass
    
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
                cancel_booking(meeting.booking_id, reason=body.reason)
            except Exception:
                # Não bloqueia o cancelamento local se o Cal.com falhar
                pass

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
