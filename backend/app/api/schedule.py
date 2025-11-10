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
        
        # Debug: mostra o estado do lead
        print(f"[SCHEDULE] Lead encontrado: name={lead.name}, email={lead.email}, company={lead.company}")
        print(f"[SCHEDULE] Request: attendeeName={body.attendeeName}, attendeeEmail={body.attendeeEmail}")
        
        attendee_name = body.attendeeName or (lead.name or "Convidado")
        attendee_email = body.attendeeEmail or (lead.email if lead.email else None)

        if not attendee_email:
            attendee_email = f"lead-{body.sessionId[:8]}@example.com"
            print(f"[SCHEDULE] ⚠️ Email do lead não encontrado, usando fallback: {attendee_email}")
        else:
            print(f"[SCHEDULE] ✅ Usando email do lead: {attendee_email}, nome: {attendee_name}")

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
                            print(f"[SCHEDULE] 🔍 Card_id encontrado no DB por email: {found_card_id}")
                            break
                
                # PRIORIDADE 2: Se não encontrou no DB, busca no Pipefy por email (mais confiável que título)
                if not found_card_id and lead.email and "@" in lead.email:
                    found_card_id = find_card_by_email(pipe_id, lead.email)
                    if found_card_id:
                        print(f"[SCHEDULE] 🔍 Card encontrado no Pipefy por email: {found_card_id}")
                
                # PRIORIDADE 3: Se não encontrou por email, busca no Pipefy pelo título (UUID)
                if not found_card_id:
                    found_card_id = find_card_by_title(pipe_id, body.sessionId[:20])
                    if found_card_id:
                        print(f"[SCHEDULE] 🔍 Card encontrado no Pipefy por título (UUID): {found_card_id}")
                
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
                    print(f"[SCHEDULE] ⚠️ Card_id do Pipefy não encontrado para sessionId {body.sessionId}, pulando update")
                    return result
            except Exception as e:
                print(f"[SCHEDULE] ⚠️ Erro ao buscar card_id do Pipefy: {e}")
                import traceback
                traceback.print_exc()
                # Continua sem atualizar Pipefy se não conseguir encontrar o card_id
        
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
                    # No Vercel, usa a URL do próprio deployment
                    base_url = os.getenv("API_BASE_URL") or os.getenv("VERCEL_URL", "http://localhost:8000")
                    if base_url and not base_url.startswith("http"):
                        base_url = f"https://{base_url}"
                    with httpx.Client(timeout=5.0) as client:
                        update_payload = {
                            "sessionId": pipefy_card_id,  # Usa o card_id encontrado, não o UUID original
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
                            print(f"[SCHEDULE] ✅ Pipefy update iniciado para card {pipefy_card_id}")
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
