import os
from typing import Dict, Optional, Any, List
import httpx

PIPEFY_API_URL = "https://api.pipefy.com/graphql"
PIPEFY_TOKEN = os.getenv("PIPEFY_TOKEN")

# IDs das fases do pipe (conforme JSON fornecido)
PHASE_AGENDADO_ID = "340909467"

# IDs dos campos (conforme JSON fornecido)
FIELD_NAMES = {
    "nome_do_lead": "nome_do_lead",
    "email_do_lead": "email_do_lead",
    "empresa_do_lead": "empresa_do_lead",
    "necessidade_do_lead": "necessidade_do_lead",
}

FIELD_MEETING = {
    "meeting_date": "meeting_date",
    "meeting_time": "meeting_time",
    "meeting_location": "meeting_location",
}

def _headers() -> Dict[str, str]:
    """Retorna headers para requisições ao Pipefy."""
    if not PIPEFY_TOKEN:
        raise ValueError("PIPEFY_TOKEN não configurado")
    return {
        "Authorization": f"Bearer {PIPEFY_TOKEN}",
        "Content-Type": "application/json",
    }

def create_pipe_webhook(
    pipe_id: str,
    webhook_url: str,
    actions: Optional[List[str]] = None,
    name: str = "SDR Webhook",
) -> Dict[str, Any]:
    """
    Cria um webhook para um pipe específico via GraphQL.
    
    Args:
        pipe_id: ID do pipe
        webhook_url: URL do webhook (ex: https://seu-backend.com/api/pipefy/webhook)
        actions: Lista de ações que disparam o webhook (padrão: ["card.create"])
        name: Nome do webhook
    
    Returns:
        Resposta da API do Pipefy com dados do webhook criado
    """
    if not PIPEFY_TOKEN:
        print("[PIPEFY] ⚠️ PIPEFY_TOKEN não configurado")
        raise ValueError("PIPEFY_TOKEN não configurado")
    
    if actions is None:
        actions = ["card.create"]
    
    mutation = """
    mutation CreatePipeWebhook($input: CreatePipeWebhookInput!) {
      createPipeWebhook(input: $input) {
        webhook {
          id
          name
          url
          actions
        }
        success
      }
    }
    """
    
    variables = {
        "input": {
            "pipe_id": pipe_id,
            "url": webhook_url,
            "actions": actions,
            "name": name,
        }
    }
    
    payload = {
        "query": mutation,
        "variables": variables,
    }
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            print(f"[PIPEFY] POST /graphql (createPipeWebhook) status: {r.status_code}")
            
            if r.status_code != 200:
                print(f"[PIPEFY] Erro na resposta: {r.text[:1000]}")
                r.raise_for_status()
            
            data = r.json()
            
            if "errors" in data:
                print(f"[PIPEFY] Erros GraphQL: {data['errors']}")
                raise RuntimeError(f"Erro GraphQL: {data['errors']}")
            
            result = data.get("data", {}).get("createPipeWebhook", {})
            print(f"[PIPEFY] ✅ Webhook criado: {result.get('webhook', {}).get('id')}")
            return result
    
    except Exception as e:
        print(f"[PIPEFY] ❌ Erro ao criar webhook: {type(e).__name__}: {str(e)}")
        raise

def _get_field_id_by_label(pipe_id: str, phase_id: str, field_label: str) -> Optional[str]:
    """
    Busca o ID interno de um campo pelo label.
    Nota: Esta função pode precisar ser ajustada dependendo da estrutura da API.
    Por enquanto, assumimos que os IDs dos campos são os mesmos que os labels.
    """
    # Em produção, você pode precisar fazer uma query para buscar os field_ids reais
    # Por enquanto, retornamos o label como ID (pode precisar ajuste)
    return field_label

def update_card_field(
    card_id: str,
    field_id: str,
    value: str,
) -> Dict[str, Any]:
    """
    Atualiza um campo específico de um card no Pipefy usando GraphQL.
    
    Args:
        card_id: ID do card no Pipefy
        field_id: ID do campo (pode ser o label ou ID interno)
        value: Valor a ser definido
    
    Returns:
        Resposta da API do Pipefy
    """
    if not PIPEFY_TOKEN:
        print("[PIPEFY] ⚠️ PIPEFY_TOKEN não configurado, usando MOCK")
        return {"mock": True, "card_id": card_id, "field_id": field_id, "value": value}

    mutation = """
    mutation UpdateCardField($cardId: ID!, $fieldId: ID!, $value: String!) {
      updateCardField(input: {
        cardId: $cardId
        fieldId: $fieldId
        value: $value
      }) {
        card {
          id
          title
        }
        success
      }
    }
    """

    variables = {
        "cardId": card_id,
        "fieldId": field_id,
        "value": value,
    }

    payload = {
        "query": mutation,
        "variables": variables,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            print(f"[PIPEFY] POST /graphql (updateCardField) status: {r.status_code}")
            
            if r.status_code != 200:
                print(f"[PIPEFY] Erro na resposta: {r.text[:1000]}")
                r.raise_for_status()
            
            data = r.json()
            
            if "errors" in data:
                print(f"[PIPEFY] Erros GraphQL: {data['errors']}")
                raise RuntimeError(f"Erro GraphQL: {data['errors']}")
            
            result = data.get("data", {}).get("updateCardField", {})
            print(f"[PIPEFY] ✅ Campo atualizado: {field_id} = {value}")
            return result

    except Exception as e:
        print(f"[PIPEFY] ❌ Erro ao atualizar campo: {type(e).__name__}: {str(e)}")
        raise

def move_card_to_phase(card_id: str, phase_id: str) -> Dict[str, Any]:
    """
    Move um card para uma fase específica no Pipefy.
    
    Args:
        card_id: ID do card no Pipefy
        phase_id: ID da fase de destino
    
    Returns:
        Resposta da API do Pipefy
    """
    if not PIPEFY_TOKEN:
        print("[PIPEFY] ⚠️ PIPEFY_TOKEN não configurado, usando MOCK")
        return {"mock": True, "card_id": card_id, "phase_id": phase_id}

    mutation = """
    mutation MoveCard($cardId: ID!, $destinationPhaseId: ID!) {
      moveCardToPhase(input: {
        cardId: $cardId
        destinationPhaseId: $destinationPhaseId
      }) {
        card {
          id
          title
          current_phase {
            id
            name
          }
        }
        success
      }
    }
    """

    variables = {
        "cardId": card_id,
        "destinationPhaseId": phase_id,
    }

    payload = {
        "query": mutation,
        "variables": variables,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            print(f"[PIPEFY] POST /graphql (moveCardToPhase) status: {r.status_code}")
            
            if r.status_code != 200:
                print(f"[PIPEFY] Erro na resposta: {r.text[:1000]}")
                r.raise_for_status()
            
            data = r.json()
            
            if "errors" in data:
                print(f"[PIPEFY] Erros GraphQL: {data['errors']}")
                raise RuntimeError(f"Erro GraphQL: {data['errors']}")
            
            result = data.get("data", {}).get("moveCardToPhase", {})
            print(f"[PIPEFY] ✅ Card movido para fase: {phase_id}")
            return result

    except Exception as e:
        print(f"[PIPEFY] ❌ Erro ao mover card: {type(e).__name__}: {str(e)}")
        raise

def update_card_lead_fields(
    card_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    need: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atualiza campos do lead no card do Pipefy.
    
    Args:
        card_id: ID do card no Pipefy
        name: Nome do lead (opcional)
        email: Email do lead (opcional)
        company: Empresa do lead (opcional)
        need: Necessidade do lead (opcional)
    
    Returns:
        Resposta da API do Pipefy
    """
    if not PIPEFY_TOKEN:
        print("[PIPEFY] ⚠️ PIPEFY_TOKEN não configurado, usando MOCK")
        return {
            "mock": True,
            "card_id": card_id,
            "updated_fields": {
                "name": bool(name),
                "email": bool(email),
                "company": bool(company),
                "need": bool(need),
            }
        }

    results = {}
    updates = []
    
    # Atualiza cada campo se fornecido
    if name:
        try:
            update_card_field(card_id, FIELD_NAMES["nome_do_lead"], name)
            results["nome_do_lead"] = "updated"
            updates.append("nome")
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao atualizar nome: {e}")
            results["nome_do_lead"] = f"error: {str(e)}"
    
    if email:
        try:
            update_card_field(card_id, FIELD_NAMES["email_do_lead"], email)
            results["email_do_lead"] = "updated"
            updates.append("email")
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao atualizar email: {e}")
            results["email_do_lead"] = f"error: {str(e)}"
    
    if company:
        try:
            update_card_field(card_id, FIELD_NAMES["empresa_do_lead"], company)
            results["empresa_do_lead"] = "updated"
            updates.append("empresa")
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao atualizar empresa: {e}")
            results["empresa_do_lead"] = f"error: {str(e)}"
    
    if need:
        try:
            update_card_field(card_id, FIELD_NAMES["necessidade_do_lead"], need)
            results["necessidade_do_lead"] = "updated"
            updates.append("necessidade")
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao atualizar necessidade: {e}")
            results["necessidade_do_lead"] = f"error: {str(e)}"
    
    if updates:
        print(f"[PIPEFY] ✅ Campos atualizados no Pipefy: {', '.join(updates)}")
    
    return results

def update_card_booking(
    card_id: str,
    meeting_date: str,
    meeting_time: str,
    meeting_location: Optional[str] = None,
    phase_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atualiza um card com informações de booking e opcionalmente move para fase "Agendado".
    
    Args:
        card_id: ID do card no Pipefy
        meeting_date: Data da reunião (formato: YYYY-MM-DD)
        meeting_time: Hora da reunião (formato: HH:MM)
        meeting_location: Link ou local da reunião (opcional)
        phase_id: ID da fase para mover (padrão: fase "Agendado")
    
    Returns:
        Resposta da API do Pipefy
    """
    if not PIPEFY_TOKEN:
        print("[PIPEFY] ⚠️ PIPEFY_TOKEN não configurado, usando MOCK")
        return {
            "mock": True,
            "card_id": card_id,
            "meeting_date": meeting_date,
            "meeting_time": meeting_time,
            "meeting_location": meeting_location,
        }

    results = {}
    
    # Atualiza campos de meeting
    try:
        # Atualiza meeting_date
        update_card_field(card_id, FIELD_MEETING["meeting_date"], meeting_date)
        results["meeting_date"] = "updated"
        
        # Atualiza meeting_time
        update_card_field(card_id, FIELD_MEETING["meeting_time"], meeting_time)
        results["meeting_time"] = "updated"
        
        # Atualiza meeting_location se fornecido
        if meeting_location:
            update_card_field(card_id, FIELD_MEETING["meeting_location"], meeting_location)
            results["meeting_location"] = "updated"
    except Exception as e:
        print(f"[PIPEFY] ⚠️ Erro ao atualizar campos: {e}")
        results["field_update_error"] = str(e)
    
    # Move para fase "Agendado" se especificado
    if phase_id:
        try:
            move_card_to_phase(card_id, phase_id)
            results["phase_moved"] = phase_id
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao mover fase: {e}")
            results["phase_move_error"] = str(e)
    
    return results

