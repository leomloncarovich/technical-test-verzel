from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
from datetime import datetime

from app.core.pipefy import update_card_booking, PHASE_AGENDADO_ID

router = APIRouter()

# -----------------------------------------------------------------------------
# Modelos de entrada
# -----------------------------------------------------------------------------

class PipefyWebhookPayload(BaseModel):
    """Payload do webhook do Pipefy quando um card é criado."""
    action: Optional[str] = None
    card: Optional[dict] = None
    data: Optional[dict] = None

class UpdateBookingIn(BaseModel):
    """Payload para atualizar booking no Pipefy."""
    sessionId: str  # card_id do Pipefy
    date: str  # formato: YYYY-MM-DD
    time: str  # formato: HH:MM
    meetLink: Optional[str] = None

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/pipefy/webhook")
async def pipefy_webhook(payload: dict):
    """
    Recebe webhook do Pipefy quando um card é criado.
    Extrai dados do lead e dispara o fluxo SDR via /api/chat.
    """
    print(f"[PIPEFY WEBHOOK] Recebido: {payload}")
    
    try:
        # Extrai dados do payload do Pipefy
        # O formato pode variar, então tentamos diferentes estruturas
        card_data = payload.get("card") or payload.get("data", {}).get("card") or payload.get("data") or {}
        
        # Extrai campos do card (pode vir em fields ou diretamente)
        fields = card_data.get("fields", [])
        field_map = {}
        
        # Converte array de fields em dict para facilitar acesso
        if isinstance(fields, list):
            for field in fields:
                field_id = field.get("field", {}).get("id") or field.get("id")
                field_value = field.get("value") or field.get("field_value", {}).get("value")
                if field_id and field_value:
                    field_map[field_id] = field_value
        elif isinstance(fields, dict):
            field_map = fields
        
        # Extrai valores dos campos conhecidos
        # Tenta pelos IDs/labels: nome_do_lead, email_do_lead, empresa_do_lead, necessidade_do_lead
        name = (
            field_map.get("nome_do_lead") or
            field_map.get("name") or
            card_data.get("title") or
            ""
        )
        email = (
            field_map.get("email_do_lead") or
            field_map.get("email") or
            ""
        )
        company = (
            field_map.get("empresa_do_lead") or
            field_map.get("company") or
            field_map.get("empresa") or
            ""
        )
        need = (
            field_map.get("necessidade_do_lead") or
            field_map.get("need") or
            field_map.get("necessidade") or
            ""
        )
        
        # Card ID é usado como sessionId
        card_id = card_data.get("id") or payload.get("card_id") or payload.get("id")
        
        if not card_id:
            raise HTTPException(status_code=400, detail="card_id não encontrado no payload")
        
        print(f"[PIPEFY WEBHOOK] Card ID: {card_id}")
        print(f"[PIPEFY WEBHOOK] Lead extraído: name={name}, email={email}, company={company}, need={need}")
        
        # Prepara payload para /api/chat
        chat_payload = {
            "sessionId": str(card_id),
            "message": "Novo lead do Pipefy",
            "lead": {
                "name": name if name else None,
                "email": email if email else None,
                "company": company if company else None,
                "need": need if need else None,
            }
        }
        
        # Chama /api/chat internamente
        # Nota: Em produção, você pode querer fazer isso de forma assíncrona
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # URL base do backend (pode ser configurada via env var)
                import os
                # No Vercel, usa a URL do próprio deployment
                base_url = os.getenv("API_BASE_URL") or os.getenv("VERCEL_URL", "http://localhost:8000")
                if base_url and not base_url.startswith("http"):
                    base_url = f"https://{base_url}"
                response = await client.post(
                    f"{base_url}/api/chat",
                    json=chat_payload
                )
                response.raise_for_status()
                chat_result = response.json()
                print(f"[PIPEFY WEBHOOK] ✅ Chat iniciado: {chat_result.get('reply', '')[:50]}...")
        except Exception as e:
            print(f"[PIPEFY WEBHOOK] ⚠️ Erro ao chamar /api/chat: {e}")
            # Não falha o webhook se o chat falhar
            raise HTTPException(
                status_code=502,
                detail=f"Erro ao iniciar chat: {str(e)}"
            )
        
        return {
            "ok": True,
            "card_id": card_id,
            "chat_initiated": True,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PIPEFY WEBHOOK] ❌ Erro ao processar webhook: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar webhook: {str(e)}")

@router.post("/pipefy/updateBooking")
def update_booking(body: UpdateBookingIn):
    """
    Atualiza o card no Pipefy quando um meeting é agendado.
    Preenche campos de meeting e move para fase "Agendado".
    """
    print(f"[PIPEFY UPDATE] Atualizando booking: sessionId={body.sessionId}, date={body.date}, time={body.time}")
    
    try:
        # Valida formato de data
        try:
            datetime.strptime(body.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")
        
        # Valida formato de hora
        try:
            datetime.strptime(body.time, "%H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de hora inválido. Use HH:MM")
        
        # Atualiza card no Pipefy
        # phase_id=None faz o código buscar dinamicamente a fase "Agendado"
        result = update_card_booking(
            card_id=body.sessionId,
            meeting_date=body.date,
            meeting_time=body.time,
            meeting_location=body.meetLink,
            phase_id=None,  # Busca dinamicamente a fase "Agendado"
        )
        
        print(f"[PIPEFY UPDATE] ✅ Card atualizado: {result}")
        
        return {
            "ok": True,
            "card_id": body.sessionId,
            "result": result,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PIPEFY UPDATE] ❌ Erro ao atualizar booking: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar booking: {str(e)}")

