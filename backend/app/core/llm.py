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
            # (opcional) limite de tokens se quiser: "max_output_tokens": 512
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
    "interestConfirmed": true|false?
  }
}

Regras:
- Descubra: nome, e-mail, empresa, necessidade/dor.
- Confirme interesse explicitamente (true/false).
- NÃO invente slots ou links. Se for oferecer, use apenas os que vierem no contexto.
- Seja conciso, profissional e empático.
- Nunca devolva nada além do JSON especificado.
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
    # Se não tiver modelo disponível, usa fallback
    if model is None:
        print("❌ MODELO NÃO INICIALIZADO - API_KEY:", "✓" if API_KEY else "✗")
        return _safe_default(user_message)

    lead = state.get("lead", {}) or {}
    context = state.get("context", {}) or {}
    slots = context.get("slots")

    try:
        ctx = {"lead_so_far": lead, "available_slots": slots}
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Contexto:\n{json.dumps(ctx, ensure_ascii=False)}\n\n"
            f"Usuário: {user_message}\n"
            f"Responda APENAS com o JSON acima, sem texto extra."
        )

        print(f"🤖 Chamando Gemini com lead: {lead}")
        resp = model.generate_content(prompt)
        text = (getattr(resp, "text", "") or "").strip()
        print(f"📥 Resposta bruta: {text[:200]}")

        # Como pedimos application/json, às vezes vem no field 'candidates[0].content.parts[0].text' mesmo.
        # Se por algum motivo vier com crase, limpa.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        data = json.loads(text)
        print(f"✅ JSON parseado: {json.dumps(data, ensure_ascii=False)[:200]}")

        # Se vier só reply, ainda aceitamos
        if "reply" in data and "action" not in data:
            data["action"] = {"type": "ASK", "reply": data["reply"]}

        # Garantias mínimas
        reply = data.get("reply") or data.get("action", {}).get("reply")
        if not reply:
            print("⚠️ Sem reply válido, usando fallback")
            return _safe_default(user_message)

        # Se tentou oferecer slots sem termos enviado, volta pra ASK
        if data.get("action", {}).get("type") == "OFFER_SLOTS" and not slots:
            data["action"] = {"type": "ASK", "reply": "Perfeito. Vou consultar a agenda e já te trago opções."}

        # Merge do lead
        lp = data.get("leadPartial") or {}
        for k, v in lp.items():
            if v is not None:
                lead[k] = v
        data["leadPartial"] = lead

        return data

    except Exception as e:
        print(f"❌ ERRO no LLM: {type(e).__name__}: {str(e)}")
        return _safe_default(user_message)
