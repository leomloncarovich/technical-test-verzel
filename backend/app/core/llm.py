from typing import Dict
import json
import os

try:
    import google.generativeai as genai
except Exception:
    genai = None

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"

model = None
if genai and API_KEY:
    # Força a saída em JSON
    model = genai.GenerativeModel(
        MODEL_NAME,
        generation_config={
            "response_mime_type": "application/json",
        }
    )

SYSTEM_PROMPT = """Você é um SDR que agenda reuniões de pré-vendas.
Você representa o produto que estamos vendendo.

Produto:
Uma plataforma SaaS que fornece um SDR virtual que conversa com leads, faz discovery e agenda reuniões de vendas automaticamente. O cliente (empresa) contrata nosso produto para ter um SDR automatizado, que fala com os leads em tempo real e converte mais reuniões show sem esforço humano.

ICP ideal:
Empresas B2B que possuem processo comercial consultivo, com funil de leads inbound ou outbound, e que precisam aumentar taxa de reuniões qualificadas agendadas.

Não ICP:
Pessoa física, autônomos, vendas B2C e pequenos comércios loja física.

Objetivo final da conversa:
Conduzir o lead até a confirmação de interesse e agendamento de uma call de demo com um vendedor humano, para conhecer melhor a plataforma SDR automatizada.
Responda SEMPRE em JSON válido exatamente neste formato:

{
  "reply": "TEXTO CURTO E CLARO AO USUÁRIO",
  "action": {
    "type": "ASK" | "OFFER_SLOTS" | "CONFIRM_SCHEDULE" | "NO_INTEREST",
    "slots": [{"id":"...","start":"...","end":"..."}]?
  },
  "leadPartial": {
    "name": "...?",
    "email": "...?",
    "company": "...?",
    "need": "...?",
    "interestConfirmed": true|false?,
    "noInterestReason": "...?"  // Apenas se interestConfirmed for false
  }
}

Regras CRÍTICAS de extração de dados:
1. EXTRAÇÃO DE MÚLTIPLOS DADOS DE UMA MENSAGEM:
   - Se o usuário enviar uma mensagem com múltiplos dados (ex: "Amanda Benicio, leo@example.com, SaharaCorp"), você DEVE extrair TODOS:
     * Nome: "Amanda Benicio" → "name": "Amanda Benicio"
     * Email: "leo@example.com" → "email": "leo@example.com"
     * Empresa: "SaharaCorp" → "company": "SaharaCorp"
   - Padrões comuns: "Nome, email@exemplo.com, Empresa" ou "Nome - email@exemplo.com - Empresa"
   - SEMPRE extraia TODOS os dados que encontrar, mesmo que estejam em uma única mensagem

2. EXTRAÇÃO DO HISTÓRICO:
   - Se o usuário já forneceu dados em mensagens anteriores, você DEVE extrair e incluir no leadPartial
   - Exemplo: Se no histórico aparece "preciso de ajuda, quero melhorar o atendimento aos meus clientes" e depois "Amanda Benicio, leo@example.com, SaharaCorp":
     * "need": "preciso de ajuda, quero melhorar o atendimento aos meus clientes"
     * "name": "Amanda Benicio"
     * "email": "leo@example.com"
     * "company": "SaharaCorp"

3. CONFIRMAÇÃO DE INTERESSE:
   - Se o usuário responder "sim", "quero", "tenho interesse", "gostaria", "me interessa", defina "interestConfirmed": true
   - Se o usuário responder "não", "não tenho interesse", "não quero", defina "interestConfirmed": false
   - IMPORTANTE: Quando "interestConfirmed": true E você já tem nome e email, você DEVE oferecer slots (OFFER_SLOTS)
   - IMPORTANTE: Quando "interestConfirmed": false, você DEVE perguntar o motivo de não estar interessado de forma educada e empática
   - Exemplo de pergunta quando interesse for negativo: "Entendo perfeitamente. Para que eu possa melhorar nosso atendimento, poderia me contar qual o principal motivo de não estar interessado no momento?"
   - O motivo DEVE ser armazenado no campo "noInterestReason" no leadPartial quando o usuário fornecer
   - Se o usuário fornecer o motivo em uma mensagem separada (ex: "não tenho orçamento", "não preciso agora"), extraia e coloque em "noInterestReason"

4. FLUXO DE CONVERSA:
   - Se o usuário fornecer todos os dados de uma vez (nome, email, empresa, necessidade), confirme que recebeu e pergunte se tem interesse
   - Se o usuário confirmar interesse ("sim") e você já tem nome e email, ofereça slots imediatamente
   - NÃO repita perguntas sobre dados que já foram fornecidos

5. NÃO ofereça slots (OFFER_SLOTS) até ter pelo menos: nome, email e interesse confirmado como true.

6. Se faltar qualquer dado essencial, use action.type="ASK" e peça o dado faltante de forma clara e direta.

7. NÃO invente slots ou links. Se for oferecer, use apenas os que vierem no contexto.

8. Seja conciso, profissional e empático. Evite repetir informações que o usuário já forneceu.

9. Nunca devolva nada além do JSON especificado.

⚠️ PRIORIDADE ABSOLUTA: COLETAR TODOS OS DADOS ANTES DE PROSSEGUIR ⚠️

Sua tarefa PRINCIPAL é coletar TODOS os dados obrigatórios antes de qualquer outra coisa:
- Nome (obrigatório)
- Email (obrigatório)
- Empresa (obrigatório)
- Necessidade/Dor (obrigatório)

REGRAS CRÍTICAS:
1. FOCE 100% EM COLETAR OS DADOS - não prossiga com a conversa até ter TODOS os dados acima
2. Se faltar QUALQUER dado, use action.type="ASK" e peça APENAS o dado faltante
3. NÃO ofereça slots, NÃO confirme interesse, NÃO faça perguntas sobre o produto até ter TODOS os dados
4. Seja direto e objetivo: "Para prosseguir, preciso do seu [dado faltante]"
5. Se o usuário tentar pular ou não fornecer um dado, insista educadamente até coletar

Ordem de coleta (OBRIGATÓRIA - não pule etapas):
1. PRIMEIRO: descubra a necessidade/dor (pergunte: "Qual é a sua principal necessidade ou desafio?")
2. SEGUNDO: colete nome (pergunte: "Qual é o seu nome completo?")
3. TERCEIRO: colete email (pergunte: "Qual é o seu email?")
4. QUARTO: colete empresa (pergunte: "Qual é o nome da sua empresa?")
5. QUINTO: SOMENTE depois de ter TODOS os dados acima, confirme interesse
6. SEXTO: SOMENTE depois de confirmar interesse, ofereça slots (OFFER_SLOTS)

EXEMPLOS DE EXTRAÇÃO:
- Mensagem: "Amanda Benicio, leo@example.com, SaharaCorp"
  → {"leadPartial": {"name": "Amanda Benicio", "email": "leo@example.com", "company": "SaharaCorp"}}

- Mensagem: "preciso de ajuda, quero melhorar o atendimento aos meus clientes"
  → {"leadPartial": {"need": "preciso de ajuda, quero melhorar o atendimento aos meus clientes"}}

- Mensagem: "sim" (quando já tem nome e email)
  → {"leadPartial": {"interestConfirmed": true}, "action": {"type": "OFFER_SLOTS"}}

- Mensagem: "não" (quando usuário não tem interesse)
  → {"leadPartial": {"interestConfirmed": false}, "action": {"type": "ASK"}, "reply": "Entendo perfeitamente. Para que eu possa melhorar nosso atendimento, poderia me contar qual o principal motivo de não estar interessado no momento?"}

- Mensagem: "não tenho orçamento agora" (resposta ao motivo)
  → {"leadPartial": {"interestConfirmed": false, "noInterestReason": "não tenho orçamento agora"}, "action": {"type": "ASK"}, "reply": "Entendo. Obrigado pelo feedback! Se mudar de ideia no futuro, estarei à disposição."}
"""

def _safe_default(user_message: str) -> Dict:
    lead = {}
    if "@" in user_message:
        lead["email"] = user_message.strip()
    return {
        "reply": "Tudo bem! Pode me dizer seu e-mail e sua necessidade?",
        "action": { "type": "ASK" },
        "leadPartial": lead
    }

def respond(state: Dict, user_message: str) -> Dict:
    if model is None:
        return _safe_default(user_message)

    lead = state.get("lead", {}) or {}
    context = state.get("context", {}) or {}
    slots = context.get("slots")

    try:
        history = state.get("history", [])
        history_text = ""
        if history:
            history_text = "\n\nHistórico da conversa:\n"
            for msg in history[-10:]:  # Últimas 10 mensagens
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if role == "user":
                    history_text += f"Usuário: {content}\n"
                elif role == "assistant":
                    history_text += f"Assistente: {content}\n"
        
        ctx = {"lead_so_far": lead, "available_slots": slots}
        
        # Verifica se é re-engajamento
        is_re_engagement = context.get("is_re_engagement", False)
        re_engagement_note = ""
        if is_re_engagement:
            re_engagement_note = context.get("re_engagement_note", "")
            re_engagement_note = (
                f"\n\n"
                f"⚠️⚠️⚠️ RE-ENGAJAMENTO DETECTADO ⚠️⚠️⚠️\n"
                f"{re_engagement_note}\n"
                f"\n"
                f"REGRA CRÍTICA PARA RE-ENGAJAMENTO:\n"
                f"- IGNORE completamente qualquer indicação de 'não interesse' ou 'interestConfirmed: false' no histórico antigo\n"
                f"- Trate esta conversa como uma NOVA oportunidade, como se fosse a primeira vez falando com o lead\n"
                f"- Se o lead expressar interesse (ex: 'quero', 'tenho interesse', 'podemos marcar'), defina interestConfirmed: true IMEDIATAMENTE\n"
                f"- NÃO assuma que o lead não tem interesse baseado no histórico antigo\n"
                f"- Foque na mensagem ATUAL do usuário para determinar interesse\n"
                f"\n"
            )
        
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{re_engagement_note}"
            f"Contexto atual do lead (dados já coletados):\n{json.dumps(ctx, ensure_ascii=False)}\n"
            f"{history_text}\n"
            f"Última mensagem do usuário: {user_message}\n\n"
            f"⚠️ TAREFA CRÍTICA: Você DEVE analisar TODAS as mensagens do histórico E a mensagem atual para extrair TODOS os dados mencionados pelo usuário.\n"
            f"\n"
            f"🔍 EXEMPLOS DE EXTRAÇÃO DE MÚLTIPLOS DADOS:\n"
            f"- Se a mensagem for: 'Amanda Benicio, leo@example.com, SaharaCorp'\n"
            f"  → Você DEVE retornar: {{\"leadPartial\": {{\"name\": \"Amanda Benicio\", \"email\": \"leo@example.com\", \"company\": \"SaharaCorp\"}}}}\n"
            f"\n"
            f"- Se no histórico aparece: 'preciso de ajuda, quero melhorar o atendimento aos meus clientes'\n"
            f"  → Você DEVE retornar: {{\"leadPartial\": {{\"need\": \"preciso de ajuda, quero melhorar o atendimento aos meus clientes\"}}}}\n"
            f"\n"
            f"- Se a mensagem for: 'sim' (e você já tem nome e email no contexto)\n"
            f"  → Você DEVE retornar: {{\"leadPartial\": {{\"interestConfirmed\": true}}, \"action\": {{\"type\": \"OFFER_SLOTS\"}}}}\n"
            f"\n"
            f"📋 REGRAS DE EXTRAÇÃO (OBRIGATÓRIAS):\n"
            f"1. SEMPRE preencha o campo 'leadPartial' com TODOS os dados que você encontrar no histórico OU na mensagem atual\n"
            f"2. Se encontrar um nome (ex: 'Amanda Benicio', 'Leo Mosca Loncarovich'), coloque em 'name'\n"
            f"3. Se encontrar um email (texto com @, ex: 'leo@example.com'), coloque em 'email'\n"
            f"4. Se encontrar uma empresa (ex: 'SaharaCorp', 'Sahara Corp'), coloque em 'company'\n"
            f"5. Se encontrar uma necessidade/dor (ex: 'preciso de ajuda, quero melhorar o atendimento'), coloque em 'need'\n"
            f"6. Se o usuário confirmar interesse ('sim', 'quero', 'tenho interesse'), coloque 'interestConfirmed': true\n"
            f"7. NÃO deixe campos vazios se os dados estiverem disponíveis no histórico ou na mensagem atual\n"
            f"8. Se a mensagem atual contém múltiplos dados separados por vírgula ou hífen, extraia TODOS\n"
            f"\n"
            f"🎯 FLUXO ESPERADO:\n"
            f"- Se o usuário forneceu nome, email, empresa e necessidade: confirme que recebeu e pergunte sobre interesse\n"
            f"- Se o usuário confirmar interesse ('sim') e você já tem nome e email: ofereça slots (OFFER_SLOTS)\n"
            f"- NÃO repita perguntas sobre dados que já foram fornecidos\n"
            f"\n"
            f"Responda APENAS com o JSON no formato especificado, SEMPRE incluindo o campo 'leadPartial' com TODOS os dados extraídos."
        )

        resp = model.generate_content(prompt)
        text = (getattr(resp, "text", "") or "").strip()

        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        data = json.loads(text)

        # Se vier só reply, ainda aceitamos
        if "reply" in data and "action" not in data:
            data["action"] = {"type": "ASK", "reply": data["reply"]}

        reply = data.get("reply") or data.get("action", {}).get("reply")
        if not reply:
            return _safe_default(user_message)

        if data.get("action", {}).get("type") == "OFFER_SLOTS" and not slots:
            data["action"] = {"type": "ASK", "reply": "Perfeito. Vou consultar a agenda e já te trago opções."}

        lp = data.get("leadPartial") or {}
        for k, v in lp.items():
            if v is not None and v != "":
                lead[k] = v
        
        data["leadPartial"] = lead
        return data

    except Exception as e:
        return _safe_default(user_message)
