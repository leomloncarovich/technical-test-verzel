import os
import re
from typing import Dict, Optional, Any, List
import httpx

PIPEFY_API_URL = "https://api.pipefy.com/graphql"
# Suporta ambos os nomes de variável para compatibilidade
PIPEFY_TOKEN = os.getenv("PIPEFY_API_TOKEN") or os.getenv("PIPEFY_TOKEN")
PIPEFY_PIPE_ID = os.getenv("PIPEFY_PIPE_ID", "306783445")

# IDs das fases do pipe (conforme JSON fornecido)
PHASE_CAIXA_ENTRADA_ID = "340909462"
PHASE_LEADS_RECEBIDOS_ID = "340909465"
PHASE_CONCLUIDO_ID = "340909464"
PHASE_AGENDADO_ID = "340909467"

# IDs dos campos do Pipefy
# NOTA: Os IDs dos campos do formulário inicial são literalmente os nomes dos campos.
# O campo motivo_nao_interesse está na fase "Não Interessado" e precisa ser buscado dinamicamente.
# IDs obtidos via buscar_field_ids.py
FIELD_NAMES: Dict[str, Optional[str]] = {
    "nome_do_lead": "nome_do_lead",           # short_text [OBRIGATÓRIO] - Formulário Inicial
    "email_do_lead": "email_do_lead",         # email [OBRIGATÓRIO] - Formulário Inicial
    "empresa_do_lead": "empresa_do_lead",     # short_text [OBRIGATÓRIO] - Formulário Inicial
    "necessidade_do_lead": "necessidade_do_lead",  # long_text [OBRIGATÓRIO] - Formulário Inicial
    "meeting_link": "meeting_link",           # short_text (opcional) - Formulário Inicial
    "meeting_datetime": "meeting_datetime",   # datetime (opcional) - Formulário Inicial
    "interesse_confirmado": "interesse_confirmado",  # radio_vertical (opcional) - Formulário Inicial
    "motivo_nao_interesse": None,   # long_text (opcional) - Fase "Não Interessado" (ID: motivo_n_o_interesse)
}

# FIELD_MEETING removido - todos os campos de meeting estão agora no formulário inicial (FIELD_NAMES)

# Cache para field IDs (evita buscar toda vez)
_FIELD_IDS_CACHE: Optional[Dict[str, str]] = None

# Flag para indicar se os field IDs foram inicializados
_FIELD_IDS_INITIALIZED = False

def _ensure_field_ids_initialized():
    """Garante que o campo motivo_nao_interesse foi inicializado (se necessário)."""
    global _FIELD_IDS_INITIALIZED
    
    if not _FIELD_IDS_INITIALIZED:
        if FIELD_NAMES.get("motivo_nao_interesse") is None:
            try:
                motivo_id = _get_field_id_by_label(PIPEFY_PIPE_ID, "motivo_nao_interesse")
                if motivo_id:
                    FIELD_NAMES["motivo_nao_interesse"] = motivo_id
                    _FIELD_IDS_INITIALIZED = True
                else:
                    _FIELD_IDS_INITIALIZED = True
            except Exception:
                _FIELD_IDS_INITIALIZED = True
        else:
            _FIELD_IDS_INITIALIZED = True

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
            if r.status_code != 200:
                r.raise_for_status()
            
            data = r.json()
            if "errors" in data:
                raise RuntimeError(f"Erro GraphQL: {data['errors']}")
            
            result = data.get("data", {}).get("createPipeWebhook", {})
            return result
    except Exception as e:
        raise

def find_card_by_title(pipe_id: str, title_pattern: str) -> Optional[str]:
    """
    Busca um card no Pipefy pelo título (ou padrão de título).
    Busca em TODAS as fases e aumenta o limite para encontrar cards mais antigos.
    
    Args:
        pipe_id: ID do pipe
        title_pattern: Padrão do título a buscar (ex: "Lead - 7d9745b4-fc66-46ab-9")
    
    Returns:
        ID do card encontrado ou None se não encontrar
    """
    if not PIPEFY_TOKEN:
        return None
    
    # Busca cards em TODAS as fases com limite maior (100 por fase)
    # Isso garante que encontre cards mesmo que estejam em outras fases
    query = """
    query FindCards($pipeId: ID!) {
      pipe(id: $pipeId) {
        phases {
          id
          name
          cards(first: 100) {
            edges {
              node {
                id
                title
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
        "pipeId": pipe_id,
    }
    
    payload = {
        "query": query,
        "variables": variables,
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            
            if r.status_code != 200:
                return None
            
            data = r.json()
            if "errors" in data:
                return None
            
            phases = data.get("data", {}).get("pipe", {}).get("phases", [])
            found_cards = []
            
            for phase in phases:
                phase_name = phase.get("name", "Unknown")
                cards = phase.get("cards", {}).get("edges", [])
                for edge in cards:
                    card = edge.get("node", {})
                    card_title = card.get("title", "")
                    if title_pattern in card_title:
                        card_id = card.get("id")
                        if card_id:
                            found_cards.append((str(card_id), phase_name))
            
            if found_cards:
                card_id, phase_name = found_cards[0]
                return card_id
            
            return None
    except Exception:
        return None

def find_card_by_email(pipe_id: str, email: str) -> Optional[str]:
    """
    Busca um card no Pipefy pelo email do lead.
    Email é único, então não pode haver duplicatas.
    Busca em TODAS as fases verificando os campos do formulário inicial.
    
    Args:
        pipe_id: ID do pipe
        email: Email do lead (obrigatório)
    
    Returns:
        ID do card encontrado ou None se não encontrar
    """
    if not PIPEFY_TOKEN:
        return None
    
    if not email:
        return None
    
    email_normalized = email.lower().strip()
    query = """
    query FindCardsByEmail($pipeId: ID!) {
      pipe(id: $pipeId) {
        phases {
          id
          name
          cards(first: 100) {
            edges {
              node {
                id
                title
                fields {
                  field {
                    id
                    label
                  }
                  value
                }
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
        "pipeId": pipe_id,
    }
    
    payload = {
        "query": query,
        "variables": variables,
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            
            if r.status_code != 200:
                return None
            
            data = r.json()
            if "errors" in data:
                return None
            
            phases = data.get("data", {}).get("pipe", {}).get("phases", [])
            found_cards = []
            
            for phase in phases:
                phase_name = phase.get("name", "Unknown")
                cards = phase.get("cards", {}).get("edges", [])
                for edge in cards:
                    card = edge.get("node", {})
                    card_id = card.get("id")
                    fields = card.get("fields", [])
                    
                    for field in fields:
                        field_obj = field.get("field", {})
                        field_label = field_obj.get("label", "").lower()
                        field_value = field.get("value", "")
                        
                        if ("email" in field_label or "e-mail" in field_label) and field_value:
                            card_email_normalized = field_value.lower().strip()
                            if email_normalized == card_email_normalized:
                                found_cards.append((str(card_id), phase_name))
                                break
            
            if found_cards:
                if len(found_cards) > 1:
                    active_cards = [c for c in found_cards if "não interessado" not in c[1].lower() and "nao interessado" not in c[1].lower()]
                    if active_cards:
                        card_id, phase_name = active_cards[0]
                        return card_id
                
                card_id, phase_name = found_cards[0]
                return card_id
            
            return None
    except Exception:
        return None

def get_pipe_phases(pipe_id: str) -> Optional[list]:
    """
    Busca todas as fases de um pipe no Pipefy.
    
    Args:
        pipe_id: ID do pipe
    
    Returns:
        Lista de fases com {id, name} ou None se não encontrar
    """
    if not PIPEFY_TOKEN:
        return None
    
    query = """
    query GetPipePhases($pipeId: ID!) {
      pipe(id: $pipeId) {
        id
        name
        phases {
          id
          name
        }
      }
    }
    """
    
    variables = {
        "pipeId": pipe_id,
    }
    
    payload = {
        "query": query,
        "variables": variables,
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            if r.status_code != 200:
                return None
            
            data = r.json()
            if "errors" in data:
                return None
            
            pipe_data = data.get("data", {}).get("pipe", {})
            phases = pipe_data.get("phases", [])
            
            if not phases:
                return None
            
            return phases
    except Exception:
        return None

def get_pipe_first_phase(pipe_id: str) -> Optional[str]:
    """
    Busca a primeira fase (fase inicial) de um pipe no Pipefy.
    Esta é a fase onde os cards criados pelo formulário inicial são colocados.
    
    Args:
        pipe_id: ID do pipe
    
    Returns:
        ID da primeira fase ou None se não encontrar
    """
    phases = get_pipe_phases(pipe_id)
    if not phases:
        return None
    
    first_phase = phases[0]
    first_phase_id = first_phase.get("id")
    return first_phase_id

def get_pipe_phase_by_name(pipe_id: str, phase_name: str) -> Optional[str]:
    """
    Busca uma fase do pipe pelo nome (case-insensitive).
    
    Args:
        pipe_id: ID do pipe
        phase_name: Nome da fase (ex: "Agendado", "Caixa de Entrada")
    
    Returns:
        ID da fase ou None se não encontrar
    """
    phases = get_pipe_phases(pipe_id)
    if not phases:
        return None
    
    phase_name_lower = phase_name.lower().strip()
    for phase in phases:
        phase_name_found = phase.get("name", "").lower().strip()
        if phase_name_found == phase_name_lower:
            phase_id = phase.get("id")
            return phase_id
    
    return None

def create_card(
    pipe_id: str,
    phase_id: Optional[str] = None,
    title: Optional[str] = None,
    fields: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Cria um novo card no Pipefy.
    
    Args:
        pipe_id: ID do pipe
        phase_id: ID da fase inicial (opcional, usa a primeira fase se não especificado)
        title: Título do card (opcional)
        fields: Dicionário com field_id -> value para preencher campos (opcional)
    
    Returns:
        Resposta da API do Pipefy com dados do card criado
    """
    if not PIPEFY_TOKEN:
        import random
        mock_id = str(random.randint(100000000, 999999999))
        return {"mock": True, "card": {"id": mock_id, "title": title or "Mock Card"}}
    
    if not phase_id:
        phase_id = get_pipe_first_phase(pipe_id)
        if not phase_id:
            phase_id = PHASE_CAIXA_ENTRADA_ID
    
    fields_input = []
    if fields:
        for field_id, value in fields.items():
            if value:
                fields_input.append({
                    "field_id": field_id,
                    "field_value": value
                })
    
    mutation = """
    mutation CreateCard($input: CreateCardInput!) {
      createCard(input: $input) {
        card {
          id
          title
          current_phase {
            id
            name
          }
        }
      }
    }
    """
    
    input_data = {
        "pipe_id": pipe_id,
        "phase_id": phase_id,
    }
    
    if title:
        input_data["title"] = title
    
    if fields_input:
        input_data["fields_attributes"] = fields_input
    
    variables = {
        "input": input_data
    }
    
    payload = {
        "query": mutation,
        "variables": variables,
    }
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            if r.status_code != 200:
                r.raise_for_status()
            
            data = r.json()
            if "errors" in data:
                raise RuntimeError(f"Erro GraphQL: {data['errors']}")
            
            result = data.get("data", {}).get("createCard", {})
            return result
    except Exception as e:
        raise

def get_pipe_fields(pipe_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca todos os campos de um pipe no Pipefy (formulário inicial e campos das fases).
    
    Args:
        pipe_id: ID do pipe
    
    Returns:
        Dict com informações dos campos ou None se não encontrar
    """
    if not PIPEFY_TOKEN:
        return None
    
    query = """
    query GetPipeFields($pipeId: ID!) {
      pipe(id: $pipeId) {
        id
        name
        start_form_fields {
          id
          label
          type
          required
          options
        }
        phases {
          id
          name
          fields {
            id
            label
            type
            required
            options
          }
        }
      }
    }
    """
    
    variables = {
        "pipeId": pipe_id,
    }
    
    payload = {
        "query": query,
        "variables": variables,
    }
    
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            if r.status_code != 200:
                return None
            
            data = r.json()
            if "errors" in data:
                return None
            
            pipe_data = data.get("data", {}).get("pipe", {})
            if not pipe_data:
                return None
            
            return pipe_data
    except Exception:
        return None

def _normalize_field_label(label: str) -> str:
    """
    Normaliza um label de campo para comparação (lowercase, remove espaços extras).
    """
    return label.lower().strip().replace(" ", "_").replace("-", "_")

def _get_field_id_by_label(pipe_id: str, field_label: str) -> Optional[str]:
    """
    Busca o ID interno de um campo pelo label.
    Primeiro tenta usar o cache, depois busca dinamicamente se necessário.
    
    Args:
        pipe_id: ID do pipe
        field_label: Label do campo (ex: "nome do lead", "email do lead")
    
    Returns:
        ID do campo ou None se não encontrar
    """
    global _FIELD_IDS_CACHE
    
    # Se o cache não foi inicializado, busca os campos
    if _FIELD_IDS_CACHE is None:
        _FIELD_IDS_CACHE = {}
        pipe_data = get_pipe_fields(pipe_id)
        if pipe_data:
            # Mapeia campos do formulário inicial
            for field in pipe_data.get("start_form_fields", []):
                field_id = field.get("id")
                field_label_normalized = _normalize_field_label(field.get("label", ""))
                if field_id and field_label_normalized:
                    _FIELD_IDS_CACHE[field_label_normalized] = field_id
                    # Também adiciona variações comuns
                    if "nome" in field_label_normalized and "lead" in field_label_normalized:
                        _FIELD_IDS_CACHE["nome_do_lead"] = field_id
                    elif "email" in field_label_normalized and "lead" in field_label_normalized:
                        _FIELD_IDS_CACHE["email_do_lead"] = field_id
                    elif "empresa" in field_label_normalized and "lead" in field_label_normalized:
                        _FIELD_IDS_CACHE["empresa_do_lead"] = field_id
                    elif "necessidade" in field_label_normalized and "lead" in field_label_normalized:
                        _FIELD_IDS_CACHE["necessidade_do_lead"] = field_id
                    elif "meeting" in field_label_normalized and "link" in field_label_normalized:
                        _FIELD_IDS_CACHE["meeting_link"] = field_id
                    elif "meeting" in field_label_normalized and ("datetime" in field_label_normalized or "date" in field_label_normalized):
                        _FIELD_IDS_CACHE["meeting_datetime"] = field_id
                    elif "interesse" in field_label_normalized and "confirmado" in field_label_normalized:
                        _FIELD_IDS_CACHE["interesse_confirmado"] = field_id
                    elif "motivo" in field_label_normalized and ("nao" in field_label_normalized or "não" in field_label_normalized) and "interesse" in field_label_normalized:
                        _FIELD_IDS_CACHE["motivo_nao_interesse"] = field_id
            
            # Mapeia campos das fases (para campos que não estão no formulário inicial)
            for phase in pipe_data.get("phases", []):
                for field in phase.get("fields", []):
                    field_id = field.get("id")
                    field_label_normalized = _normalize_field_label(field.get("label", ""))
                    if field_id and field_label_normalized:
                        # Só adiciona se não estiver no cache (formulário inicial tem prioridade)
                        if field_label_normalized not in _FIELD_IDS_CACHE:
                            _FIELD_IDS_CACHE[field_label_normalized] = field_id
                        
                        # Busca especial para motivo_nao_interesse (pode estar em fase específica)
                        if "motivo" in field_label_normalized and ("nao" in field_label_normalized or "não" in field_label_normalized or "n_o" in field_label_normalized) and "interesse" in field_label_normalized:
                            if "motivo_nao_interesse" not in _FIELD_IDS_CACHE:
                                _FIELD_IDS_CACHE["motivo_nao_interesse"] = field_id
                                print(f"[PIPEFY] ✅ Campo 'motivo_nao_interesse' encontrado na fase '{phase.get('name', '')}': {field.get('label', '')} -> {field_id}")
            
            print(f"[PIPEFY] ✅ Cache de field IDs inicializado com {len(_FIELD_IDS_CACHE)} campos")
            if _FIELD_IDS_CACHE:
                print(f"[PIPEFY] 💡 Campos encontrados: {list(_FIELD_IDS_CACHE.keys())[:10]}...")
    
    # Normaliza o label fornecido
    field_label_normalized = _normalize_field_label(field_label)
    
    # Tenta encontrar no cache
    if field_label_normalized in _FIELD_IDS_CACHE:
        return _FIELD_IDS_CACHE[field_label_normalized]
    
    # Tenta variações comuns
    variations = [
        field_label_normalized,
        field_label_normalized.replace("_", " "),
        field_label_normalized.replace("_", "-"),
    ]
    
    for variation in variations:
        if variation in _FIELD_IDS_CACHE:
            return _FIELD_IDS_CACHE[variation]
    
    # Se não encontrou, retorna None (o código pode usar o label como fallback)
    print(f"[PIPEFY] ⚠️ Campo '{field_label}' não encontrado no cache. Usando label como fallback.")
    return None

def initialize_field_ids(pipe_id: Optional[str] = None) -> Dict[str, str]:
    """
    Inicializa apenas o campo motivo_nao_interesse (que está em fase específica).
    Os outros campos já estão com IDs conhecidos (são os próprios nomes).
    
    Args:
        pipe_id: ID do pipe (usa PIPEFY_PIPE_ID se não fornecido)
    
    Returns:
        Dict com os field IDs atualizados
    """
    global FIELD_NAMES, _FIELD_IDS_INITIALIZED
    
    if not pipe_id:
        pipe_id = PIPEFY_PIPE_ID
    
    print(f"[PIPEFY] 🔄 Buscando campo 'motivo_nao_interesse' para pipe {pipe_id}...")
    
    # Apenas busca motivo_nao_interesse (está na fase "Não Interessado")
    motivo_id = _get_field_id_by_label(pipe_id, "motivo_nao_interesse")
    if motivo_id:
        FIELD_NAMES["motivo_nao_interesse"] = motivo_id
        print(f"[PIPEFY] ✅ Campo 'motivo_nao_interesse' encontrado: {motivo_id}")
    else:
        print(f"[PIPEFY] ⚠️ Campo 'motivo_nao_interesse' não encontrado. Pode não existir no pipe.")
    
    _FIELD_IDS_INITIALIZED = True
    return FIELD_NAMES

def update_card_field(
    card_id: str,
    field_id: str,
    value: str,
) -> Dict[str, Any]:
    """
    Atualiza um campo específico de um card no Pipefy usando GraphQL.
    Tenta resolver o field_id dinamicamente se for um label.
    
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

    # Tenta resolver o field_id dinamicamente se for um label
    resolved_field_id = _get_field_id_by_label(PIPEFY_PIPE_ID, field_id)
    if resolved_field_id:
        # Se encontrou um ID real, usa ele
        actual_field_id = resolved_field_id
        print(f"[PIPEFY] 🔍 Field ID resolvido: '{field_id}' -> '{actual_field_id}'")
    else:
        # Se não encontrou, usa o valor original (pode ser um ID numérico direto)
        actual_field_id = field_id
        # Verifica se parece ser um ID numérico (Pipefy IDs são numéricos)
        if not field_id.isdigit():
            print(f"[PIPEFY] ⚠️ Campo '{field_id}' não encontrado no cache. Tentando usar como ID direto.")

    mutation = """
    mutation UpdateCardField($input: UpdateCardFieldInput!) {
      updateCardField(input: $input) {
        card {
          id
          title
        }
      }
    }
    """

    input_data = {
        "card_id": card_id,
        "field_id": actual_field_id,
        "new_value": value,  # Pipefy usa "new_value" no UpdateCardFieldInput
    }
    
    variables = {
        "input": input_data,
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
            print(f"[PIPEFY] ✅ Campo atualizado: {actual_field_id} = {value}")
            return result

    except Exception as e:
        print(f"[PIPEFY] ❌ Erro ao atualizar campo: {type(e).__name__}: {str(e)}")
        raise

def update_card_title(card_id: str, title: str) -> Dict[str, Any]:
    """
    Atualiza o título de um card no Pipefy usando GraphQL.
    
    Args:
        card_id: ID do card no Pipefy
        title: Novo título do card
    
    Returns:
        Resposta da API do Pipefy
    """
    if not PIPEFY_TOKEN:
        print("[PIPEFY] ⚠️ PIPEFY_TOKEN não configurado, usando MOCK")
        return {"mock": True, "card_id": card_id, "title": title}

    mutation = """
    mutation UpdateCard($input: UpdateCardInput!) {
      updateCard(input: $input) {
        card {
          id
          title
        }
      }
    }
    """

    input_data = {
        "id": card_id,
        "title": title,
    }
    
    variables = {
        "input": input_data,
    }

    payload = {
        "query": mutation,
        "variables": variables,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            print(f"[PIPEFY] POST /graphql (updateCard) status: {r.status_code}")
            
            if r.status_code != 200:
                print(f"[PIPEFY] Erro na resposta: {r.text[:1000]}")
                r.raise_for_status()
            
            data = r.json()
            
            if "errors" in data:
                print(f"[PIPEFY] Erros GraphQL: {data['errors']}")
                raise RuntimeError(f"Erro GraphQL: {data['errors']}")
            
            result = data.get("data", {}).get("updateCard", {})
            print(f"[PIPEFY] ✅ Título do card atualizado: {title}")
            return result

    except Exception as e:
        print(f"[PIPEFY] ⚠️ Erro ao atualizar título do card: {type(e).__name__}: {str(e)}")
        # Não levanta exceção, apenas loga o erro (título não é crítico)
        return {}

def get_card_current_phase(card_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca a fase atual de um card no Pipefy.
    
    Args:
        card_id: ID do card no Pipefy
    
    Returns:
        Dict com informações da fase atual ou None se não encontrar
    """
    if not PIPEFY_TOKEN:
        return None
    
    query = """
    query GetCard($cardId: ID!) {
      card(id: $cardId) {
        id
        title
        current_phase {
          id
          name
        }
      }
    }
    """
    
    variables = {
        "cardId": card_id,
    }
    
    payload = {
        "query": query,
        "variables": variables,
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(PIPEFY_API_URL, headers=_headers(), json=payload)
            if r.status_code != 200:
                return None
            
            data = r.json()
            if "errors" in data:
                return None
            
            card = data.get("data", {}).get("card", {})
            return card.get("current_phase")
    except Exception:
        return None

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

    # Verifica a fase atual do card antes de tentar mover
    current_phase = get_card_current_phase(card_id)
    if current_phase:
        current_phase_id = current_phase.get("id")
        current_phase_name = current_phase.get("name", "Desconhecida")
        print(f"[PIPEFY] 📍 Fase atual do card {card_id}: {current_phase_name} (ID: {current_phase_id})")
        print(f"[PIPEFY] 🎯 Tentando mover para fase: {phase_id}")
        
        # Se já está na fase de destino, não precisa mover
        if current_phase_id == phase_id:
            print(f"[PIPEFY] ✅ Card já está na fase de destino, não é necessário mover")
            return {"already_in_phase": True, "card_id": card_id, "phase_id": phase_id, "current_phase": current_phase}
    else:
        print(f"[PIPEFY] ⚠️ Não foi possível obter a fase atual do card {card_id}")

    mutation = """
    mutation MoveCard($input: MoveCardToPhaseInput!) {
      moveCardToPhase(input: $input) {
        card {
          id
          title
          current_phase {
            id
            name
          }
        }
      }
    }
    """

    input_data = {
        "card_id": card_id,
        "destination_phase_id": phase_id,
    }
    
    variables = {
        "input": input_data,
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
                errors = data['errors']
                print(f"[PIPEFY] Erros GraphQL: {errors}")
                # Verifica se o erro é porque o card já está na fase ou transição não permitida
                error_msg = str(errors[0].get("message", "")) if errors else ""
                error_code = str(errors[0].get("extensions", {}).get("code", "")) if errors else ""
                
                if "Cannot move" in error_msg or "PHASE_TRANSITION_ERROR" in error_code:
                    print(f"[PIPEFY] ⚠️ Não foi possível mover o card de '{current_phase_name if current_phase else 'desconhecida'}' para fase {phase_id}")
                    print(f"[PIPEFY] ⚠️ Erro: {error_msg}")
                    print(f"[PIPEFY] 💡 Possíveis causas:")
                    print(f"[PIPEFY]   1. O card precisa passar por uma fase intermediária")
                    print(f"[PIPEFY]   2. O workflow do Pipefy não permite esta transição direta")
                    print(f"[PIPEFY]   3. O ID da fase de destino ({phase_id}) pode estar incorreto")
                    # Retorna um resultado parcial em vez de lançar exceção
                    return {"warning": error_msg, "card_id": card_id, "phase_id": phase_id, "current_phase": current_phase}
                raise RuntimeError(f"Erro GraphQL: {errors}")
            
            result = data.get("data", {}).get("moveCardToPhase", {})
            card_result = result.get("card", {})
            new_phase = card_result.get("current_phase", {})
            print(f"[PIPEFY] ✅ Card movido para fase: {new_phase.get('name', 'Desconhecida')} (ID: {new_phase.get('id')})")
            return result

    except Exception as e:
        print(f"[PIPEFY] ❌ Erro ao mover card: {type(e).__name__}: {str(e)}")
        raise

def move_card_to_no_interest_phase(card_id: str, phase_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Move um card para a fase "Não Interessado" quando o lead não tem interesse.
    
    Args:
        card_id: ID do card no Pipefy
        phase_id: ID da fase "Não Interessado" (se None, busca dinamicamente)
    
    Returns:
        Dict com resultado da operação
    """
    if not PIPEFY_TOKEN:
        print("[PIPEFY] ⚠️ PIPEFY_TOKEN não configurado, usando MOCK")
        return {
            "mock": True,
            "card_id": card_id,
            "phase": "Não Interessado",
        }
    
    results = {}
    
    # Se phase_id não foi especificado, busca dinamicamente a fase "Não Interessado"
    if not phase_id:
        phase_id = get_pipe_phase_by_name(PIPEFY_PIPE_ID, "Não Interessado")
        if not phase_id:
            # Tenta variações do nome
            phase_id = get_pipe_phase_by_name(PIPEFY_PIPE_ID, "Não interessado")
            if not phase_id:
                phase_id = get_pipe_phase_by_name(PIPEFY_PIPE_ID, "Sem Interesse")
                if not phase_id:
                    print(f"[PIPEFY] ⚠️ Não foi possível encontrar fase 'Não Interessado' no pipe")
                    results["phase_not_found"] = True
                    return results
    
    if phase_id:
        try:
            # Verifica a fase atual do card
            current_phase = get_card_current_phase(card_id)
            current_phase_id = current_phase.get("id") if current_phase else None
            current_phase_name = current_phase.get("name") if current_phase else "desconhecida"
            
            # Se já está na fase "Não Interessado", não precisa mover
            if current_phase_id == phase_id:
                print(f"[PIPEFY] ✅ Card já está na fase 'Não Interessado'")
                results["already_in_phase"] = True
                return results
            
            print(f"[PIPEFY] 🔄 Movendo card {card_id} de '{current_phase_name}' para 'Não Interessado'")
            
            # Tenta mover para "Não Interessado"
            move_result = move_card_to_phase(card_id, phase_id)
            
            if "warning" in move_result:
                warning_msg = move_result.get("warning", "")
                print(f"[PIPEFY] ⚠️ Não foi possível mover card para 'Não Interessado': {warning_msg}")
                print(f"[PIPEFY] 💡 Verifique se o workflow do Pipefy permite transição para 'Não Interessado'")
                results["phase_move_warning"] = warning_msg
            elif "already_in_phase" in move_result:
                print(f"[PIPEFY] ✅ Card já está na fase 'Não Interessado'")
                results["already_in_phase"] = True
            else:
                print(f"[PIPEFY] ✅ Card movido para 'Não Interessado'")
                results["phase_moved"] = phase_id
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao mover card para 'Não Interessado': {e}")
            results["phase_move_error"] = str(e)
    
    return results

def update_card_lead_fields(
    card_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    need: Optional[str] = None,
    interest_confirmed: Optional[bool] = None,
    no_interest_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atualiza campos do lead no card do Pipefy.
    
    Args:
        card_id: ID do card no Pipefy
        name: Nome do lead (opcional)
        email: Email do lead (opcional)
        company: Empresa do lead (opcional)
        need: Necessidade do lead (opcional)
        interest_confirmed: Se o lead confirmou interesse (opcional, boolean)
        no_interest_reason: Motivo de não interesse (opcional, usado quando interest_confirmed = False)
    
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

    # Garante que os field IDs foram inicializados
    _ensure_field_ids_initialized()
    
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
    
    # Atualiza interesse confirmado se fornecido e se o campo existir no Pipefy
    # Campo é do tipo radio_vertical - usa valores "Sim"/"Não" ou conforme opções configuradas
    if interest_confirmed is not None:
        interesse_field_id = FIELD_NAMES.get("interesse_confirmado")
        if interesse_field_id:
            try:
                # Campo radio_vertical geralmente aceita "Sim"/"Não" ou valores das opções configuradas
                # Se o campo tiver outras opções, ajuste aqui conforme necessário
                value = "Sim" if interest_confirmed else "Não"
                update_card_field(card_id, interesse_field_id, value)
                results["interesse_confirmado"] = "updated"
                updates.append("interesse_confirmado")
                
                # Se o interesse for False, move o card para fase "Não Interessado"
                if not interest_confirmed:
                    print(f"[PIPEFY] 🔄 Interesse confirmado como False, movendo card para fase 'Não Interessado'")
                    move_result = move_card_to_no_interest_phase(card_id)
                    if "phase_moved" in move_result:
                        results["moved_to_no_interest"] = True
                        print(f"[PIPEFY] ✅ Card movido para fase 'Não Interessado'")
                    elif "phase_not_found" in move_result:
                        print(f"[PIPEFY] ⚠️ Fase 'Não Interessado' não encontrada no pipe. Crie essa fase no Pipefy.")
                        results["no_interest_phase_not_found"] = True
                    elif "phase_move_warning" in move_result:
                        print(f"[PIPEFY] ⚠️ Não foi possível mover para 'Não Interessado': {move_result.get('phase_move_warning')}")
                        results["no_interest_move_warning"] = move_result.get("phase_move_warning")
            except Exception as e:
                print(f"[PIPEFY] ⚠️ Erro ao atualizar interesse confirmado: {e}")
                print(f"[PIPEFY] 💡 Verifique se o campo radio_vertical aceita 'Sim'/'Não' ou se precisa de outros valores")
                results["interesse_confirmado"] = f"error: {str(e)}"
        else:
            print(f"[PIPEFY] ⚠️ Campo 'interesse_confirmado' não configurado em FIELD_NAMES")
    
    # Atualiza motivo de não interesse SEMPRE quando interesse for False
    # Se não houver motivo específico, usa um valor padrão
    if interest_confirmed is False:
        motivo_field_id = FIELD_NAMES.get("motivo_nao_interesse")
        
        # Se não encontrou no FIELD_NAMES, tenta buscar dinamicamente
        if not motivo_field_id:
            print(f"[PIPEFY] 🔍 Campo 'motivo_nao_interesse' não encontrado em FIELD_NAMES, tentando buscar dinamicamente...")
            motivo_field_id = _get_field_id_by_label(PIPEFY_PIPE_ID, "motivo_nao_interesse")
            if motivo_field_id:
                # Atualiza FIELD_NAMES para cache
                FIELD_NAMES["motivo_nao_interesse"] = motivo_field_id
                print(f"[PIPEFY] ✅ Campo 'motivo_nao_interesse' encontrado dinamicamente: {motivo_field_id}")
        
        if motivo_field_id:
            # Se não foi fornecido um motivo, usa um padrão
            motivo_to_update = no_interest_reason if no_interest_reason else "Não especificado pelo lead"
            
            try:
                print(f"[PIPEFY] 🔄 Atualizando campo 'motivo_nao_interesse' (field_id={motivo_field_id}) com valor: {motivo_to_update[:100]}...")
                update_card_field(card_id, motivo_field_id, motivo_to_update)
                results["motivo_nao_interesse"] = "updated"
                updates.append("motivo_nao_interesse")
                print(f"[PIPEFY] ✅ Motivo de não interesse atualizado com sucesso no card {card_id}: {motivo_to_update[:50]}...")
            except Exception as e:
                print(f"[PIPEFY] ⚠️ Erro ao atualizar motivo de não interesse: {type(e).__name__}: {str(e)}")
                print(f"[PIPEFY] 💡 Verifique se o field_id '{motivo_field_id}' está correto e se o campo existe no Pipefy")
                print(f"[PIPEFY] 💡 O field_id atual é: '{motivo_field_id}' (pode ser que precise ser o ID numérico do campo)")
                import traceback
                traceback.print_exc()
                results["motivo_nao_interesse"] = f"error: {str(e)}"
        else:
            print(f"[PIPEFY] ⚠️ Campo 'motivo_nao_interesse' não encontrado no Pipefy")
            print(f"[PIPEFY] 💡 Verifique se o campo existe no formulário inicial do Pipefy com um dos seguintes nomes:")
            print(f"[PIPEFY]    - 'motivo não interesse'")
            print(f"[PIPEFY]    - 'motivo de não interesse'")
            print(f"[PIPEFY]    - 'razão do não interesse'")
            print(f"[PIPEFY]    - ou similar")
            print(f"[PIPEFY] 💡 O campo deve estar no formulário inicial (start_form_fields) do pipe")
    elif no_interest_reason:
        # Se interesse não é False mas há um motivo (caso raro), também atualiza
        motivo_field_id = FIELD_NAMES.get("motivo_nao_interesse")
        if motivo_field_id:
            try:
                print(f"[PIPEFY] 🔄 Atualizando campo 'motivo_nao_interesse' (field_id={motivo_field_id}) com valor: {no_interest_reason[:100]}...")
                update_card_field(card_id, motivo_field_id, no_interest_reason)
                results["motivo_nao_interesse"] = "updated"
                updates.append("motivo_nao_interesse")
                print(f"[PIPEFY] ✅ Motivo de não interesse atualizado com sucesso no card {card_id}")
            except Exception as e:
                print(f"[PIPEFY] ⚠️ Erro ao atualizar motivo de não interesse: {type(e).__name__}: {str(e)}")
                results["motivo_nao_interesse"] = f"error: {str(e)}"
    
    # Atualiza o título do card se tiver nome e email/empresa
    # IMPORTANTE: Sempre atualiza o título no final para garantir que não seja sobrescrito
    # Formato: "Nome - Email" ou "Nome - Empresa" (se não tiver email)
    # Isso garante que o título nunca seja "Sim" ou "Não" (valores do campo interesse_confirmado)
    # NOTA: Não preserva o UUID no título - atualiza para "Nome - Email" limpo
    if name and (email or company):
        try:
            # Gera o título no formato "Nome - Email" ou "Nome - Empresa" (sem UUID)
            if email and "@" in email:
                new_title = f"{name.strip()} - {email.strip()}"
            elif company:
                new_title = f"{name.strip()} - {company.strip()}"
            else:
                new_title = name.strip()
            
            # Atualiza o título no final para garantir que não seja sobrescrito por outros campos
            update_card_title(card_id, new_title)
            results["title"] = "updated"
            print(f"[PIPEFY] ✅ Título do card atualizado: {new_title}")
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao atualizar título do card: {e}")
            # Não adiciona erro aos results pois título não é crítico
    
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

    # Garante que os field IDs foram inicializados
    _ensure_field_ids_initialized()
    
    results = {}
    
    # Atualiza campos de meeting no formulário inicial (todos estão em FIELD_NAMES agora)
    try:
        # Campo meeting_datetime é do tipo datetime no Pipefy
        # Formato ISO: "2025-11-10T14:30:00" ou "2025-11-10 14:30:00"
        # Pipefy aceita formato ISO 8601 para campos datetime
        from datetime import datetime as dt
        try:
            # Tenta criar datetime a partir de date e time
            dt_obj = dt.strptime(f"{meeting_date} {meeting_time}", "%Y-%m-%d %H:%M")
            # Formato ISO 8601 para Pipefy datetime
            meeting_datetime_iso = dt_obj.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            # Fallback: formato simples se parsing falhar
            meeting_datetime_iso = f"{meeting_date} {meeting_time}:00"
        
        update_card_field(card_id, FIELD_NAMES["meeting_datetime"], meeting_datetime_iso)
        results["meeting_datetime"] = "updated"
        
        # Atualiza meeting_link no formulário inicial se fornecido
        if meeting_location:
            update_card_field(card_id, FIELD_NAMES["meeting_link"], meeting_location)
            results["meeting_link"] = "updated"
    except Exception as e:
        print(f"[PIPEFY] ⚠️ Erro ao atualizar campos: {e}")
        results["field_update_error"] = str(e)
    
    # Move para fase "Agendado" se especificado
    # Fluxo simplificado: "Caixa de entrada" → "Agendado" (direto)
    # NOTA: Os campos da fase "Caixa de entrada" (Prioridade, Data de entrada, Responsável, Status, Anexos)
    # não precisam ser preenchidos - são campos manuais/opcionais
    # Se phase_id não foi especificado, busca dinamicamente a fase "Agendado"
    if not phase_id:
        phase_id = get_pipe_phase_by_name(PIPEFY_PIPE_ID, "Agendado")
        if not phase_id:
            # Fallback: tenta usar o ID antigo se a busca falhar
            print(f"[PIPEFY] ⚠️ Não foi possível buscar fase 'Agendado', usando fallback")
            phase_id = PHASE_AGENDADO_ID
    
    if phase_id:
        try:
            # Verifica a fase atual do card
            current_phase = get_card_current_phase(card_id)
            current_phase_id = current_phase.get("id") if current_phase else None
            
            # Tenta mover diretamente para "Agendado"
            # Se o workflow do Pipefy permitir transição direta, funcionará
            # Se não permitir, o erro será registrado e o card ficará em "Caixa de entrada"
            move_result = move_card_to_phase(card_id, phase_id)
            
            if "warning" in move_result:
                warning_msg = move_result.get("warning", "")
                print(f"[PIPEFY] ⚠️ Não foi possível mover card para 'Agendado': {warning_msg}")
                print(f"[PIPEFY] 💡 Verifique se o workflow do Pipefy permite transição direta de 'Caixa de entrada' para 'Agendado'")
                results["phase_move_warning"] = warning_msg
            elif "already_in_phase" in move_result:
                print(f"[PIPEFY] ✅ Card já está na fase 'Agendado'")
                results["phase_already_in_destination"] = True
            else:
                print(f"[PIPEFY] ✅ Card movido de 'Caixa de entrada' para 'Agendado'")
                results["phase_moved"] = phase_id
        except Exception as e:
            print(f"[PIPEFY] ⚠️ Erro ao mover fase: {e}")
            results["phase_move_error"] = str(e)
    
    return results

