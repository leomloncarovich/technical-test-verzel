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
    init_db,
    get_lead_by_session,
    merge_lead,
)
from app.core.calendar import get_slots   # Cal.com ou mock, conforme .env
from app.core.pipefy import update_card_lead_fields

# -----------------------------------------------------------------------------
# Config & setup
# -----------------------------------------------------------------------------
init_db()
router = APIRouter()

BRT = ZoneInfo("America/Sao_Paulo")

class ChatIn(BaseModel):
    message: str
    sessionId: str

def load_history(db, session_id: str, limit: int = 20) -> List[dict]:
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.ts.asc())
    rows = db.exec(stmt).all()
    return [{"role": m.role, "content": m.content, "ts": m.ts.isoformat()} for m in rows][-limit:]

# -----------------------------------------------------------------------------
# Utilitários de tempo / filtro
# -----------------------------------------------------------------------------
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
        # Parse mais robusto do ISO string
        slot_start_str = s.get("start", "")
        if not slot_start_str:
            continue
        # Normaliza timezone
        if slot_start_str.endswith("Z"):
            slot_start_str = slot_start_str[:-1] + "+00:00"
        try:
            dt_start = datetime.fromisoformat(slot_start_str).astimezone(BRT)
            if start_brt <= dt_start < end_brt:
                out.append(s)
            else:
                print(f"[FILTER] Slot {s.get('id', '?')} fora da janela: {dt_start} (BRT) não está entre {start_brt} e {end_brt}")
        except Exception as e:
            print(f"[FILTER] Erro ao parsear slot {s.get('id', '?')}: {slot_start_str} - {e}")
    return out

def clamp_after_hour(slots: List[dict], h_min: int) -> List[dict]:
    """Garante slots >= h_min em BRT (ex.: 'a partir das 15')."""
    out = []
    for s in slots:
        try:
            hour = _brt_hour_from_iso(s["start"])
            if hour >= h_min:
                out.append(s)
            else:
                print(f"[CLAMP] Slot {s.get('id', '?')} removido: hora {hour} < {h_min}")
        except Exception as e:
            print(f"[CLAMP] Erro ao processar slot {s.get('id', '?')}: {e}")
            # Mantém o slot se não conseguir processar
            out.append(s)
    return out

def _is_pipefy_card_id(session_id: str) -> bool:
    """
    Verifica se sessionId parece ser um card_id do Pipefy.
    Card IDs do Pipefy são geralmente numéricos e longos.
    """
    if not session_id:
        return False
    # Pipefy card IDs são geralmente numéricos (string numérica)
    # Pode ser um número grande (ex: "123456789")
    return session_id.isdigit() and len(session_id) >= 6

def prioritize_slots(slots: List[dict], alvo_h: Optional[int]) -> List[dict]:
    """Ordena por distância à hora alvo (em BRT) se houver alvo."""
    if alvo_h is None or not slots:
        return slots
    return sorted(
        slots,
        key=lambda s: abs(_brt_hour_from_iso(s["start"]) - alvo_h) + (_brt_minute_from_iso(s["start"]) / 60.0)
    )

# -----------------------------------------------------------------------------
# Parser de data/hora em pt-BR com preferências
# -----------------------------------------------------------------------------
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

    # dia da semana
    m = re.search(r"(pr[óo]xima?|na|no)\s+(segunda|ter[çc]a|quarta|quinta|sexta|s[áa]bado|domingo)", t)
    if m:
        wd = WEEKDAYS[m.group(2)]
        nxt = _next_weekday(base, wd, include_today=("hoje" in t))
        return datetime.combine(nxt, time(0,0), tzinfo=BRT), mentions_tomorrow

    # "dia 10"
    m = re.search(r"\bdia\s+(\d{1,2})\b", t)
    if m:
        d = int(m.group(1))
        month = now.month
        year = now.year
        try:
            return datetime(year, month, d, 0, 0, tzinfo=BRT), mentions_tomorrow
        except ValueError:
            pass

    # dd/mm(/aaaa)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        d, mo, yr = int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else now.year
        # normaliza ano 2 dígitos
        if yr < 100:
            yr += 2000
        try:
            return datetime(yr, mo, d, 0, 0, tzinfo=BRT), mentions_tomorrow
        except ValueError:
            pass

    # default: hoje
    return datetime.combine(base, time(0,0), tzinfo=BRT), mentions_tomorrow

def parse_time_prefs_pt(text: str) -> Tuple[Optional[int], Optional[int], Optional[int], str]:
    """
    Retorna (start_h, end_h, alvo_h, modo)
    modo: "range" | "after" | "around" | "period" | "none"
    Regras: entende manhã/tarde; 'a partir/após/depois de X'; 'X até Y';
            'próximo/perto/às X'; hora solta '15' como fallback.
    """
    t_raw = (text or "").lower()

    # limpar números de DATA para não virar "hora"
    t = re.sub(r"\bdia\s+\d{1,2}\b", "", t_raw)                       # remove "dia 07"
    t = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", "", t)             # remove "dd/mm(/aaaa)"
    t = re.sub(r"\s+", " ", t).strip()

    # períodos do dia
    if any(k in t for k in ["manhã","manha","de manhã","de manha"]):
        return 8, 12, None, "period"
    if any(k in t for k in ["tarde","à tarde","a tarde","depois do almoço","mais tarde"]):
        return 13, 18, None, "period"

    # "a partir / após / depois" de X (aceita da/das/as/às)
    m = re.search(r"(a partir|ap[óo]s|depois)\s+(?:d?[àa]s?\s*)?(\d{1,2})h?", t)
    if m:
        h = min(max(int(m.group(2)), 0), 23)
        return h, 20, h, "after"

    # "X até Y"
    nums = re.findall(r"\b(\d{1,2})h?\b", t)
    if "até" in t and len(nums) >= 2:
        h1, h2 = int(nums[0]), int(nums[1])
        return min(h1, h2), max(h1, h2), (h1 + h2)//2, "range"

    # "próximo/perto/às X"
    m = re.search(r"(pr[óo]ximo|perto|[àa]s?)\s*(\d{1,2})h?", t)
    if m:
        h = min(max(int(m.group(2)), 0), 23)
        return max(8, h-2), min(20, h+2), h, "around"

    # hora solta (pega a ÚLTIMA ocorrência para favorecer a que vem depois da data)
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

    # defaults
    if sh is None and eh is None:
        sh, eh = (13, 18) if said_tomorrow else (9, 18)

    start_brt = datetime.combine(base_brt.date(), time(sh, 0, tzinfo=BRT))
    end_brt   = datetime.combine(base_brt.date(), time(eh, 0, tzinfo=BRT))
    start_utc = start_brt.astimezone(timezone.utc)
    end_utc   = end_brt.astimezone(timezone.utc)

    fallbacks: List[Tuple[datetime,datetime]] = []

    # se não disse "amanhã": fallback = mesma janela no próximo dia
    if not said_tomorrow:
        fs = (start_brt + timedelta(days=1)).astimezone(timezone.utc)
        fe = (end_brt + timedelta(days=1)).astimezone(timezone.utc)
        fallbacks.append((fs, fe))

    # fallback final: dia inteiro (amanhã se não disse "amanhã")
    whole = base_brt.date() if said_tomorrow else (base_brt + timedelta(days=1)).date()
    ws = datetime.combine(whole, time(0,0), tzinfo=BRT).astimezone(timezone.utc)
    we = datetime.combine(whole, time(23,59,59), tzinfo=BRT).astimezone(timezone.utc)
    fallbacks.append((ws, we))

    return start_utc, end_utc, alvo, modo, fallbacks

# -----------------------------------------------------------------------------
# Handler principal
# -----------------------------------------------------------------------------
@router.post("/chat")
def chat(body: ChatIn):
    with get_session() as db:
        # salva mensagem do usuário
        db.add(Message(session_id=body.sessionId, role="user", content=body.message))
        db.commit()

        # carrega lead + histórico
        lead = get_lead_by_session(db, body.sessionId)
        history = load_history(db, body.sessionId)

        def build_state(slots=None):
            return {
                "lead": {
                    "name": lead.name,
                    "email": lead.email,
                    "company": lead.company,
                    "need": lead.need,
                    "interestConfirmed": lead.interest_confirmed,
                },
                "context": {"slots": slots} if slots else {},
                "history": history,
            }

        # 1ª rodada do LLM (sem slots)
        resp = llm.respond(build_state(), body.message)

        # mescla lead parcial
        merged = merge_lead(lead, resp.get("leadPartial") or {})
        db.add(merged)
        db.commit()
        
        # Sincroniza com Pipefy se sessionId for um card_id do Pipefy
        # Verifica se houve mudanças nos dados do lead
        lead_partial = resp.get("leadPartial") or {}
        if lead_partial and _is_pipefy_card_id(body.sessionId):
            # Detecta quais campos foram atualizados
            name_updated = "name" in lead_partial and lead_partial["name"] and lead_partial["name"] != lead.name
            email_updated = "email" in lead_partial and lead_partial["email"] and lead_partial["email"] != lead.email
            company_updated = "company" in lead_partial and lead_partial["company"] and lead_partial["company"] != lead.company
            need_updated = "need" in lead_partial and lead_partial["need"] and lead_partial["need"] != lead.need
            
            if name_updated or email_updated or company_updated or need_updated:
                # Atualiza Pipefy de forma não-bloqueante
                try:
                    # Usa valores do merged (já atualizado)
                    update_card_lead_fields(
                        card_id=body.sessionId,
                        name=merged.name if name_updated else None,
                        email=merged.email if email_updated else None,
                        company=merged.company if company_updated else None,
                        need=merged.need if need_updated else None,
                    )
                    print(f"[CHAT] ✅ Dados do lead sincronizados com Pipefy (card {body.sessionId})")
                except Exception as e:
                    # Não bloqueia o chat se Pipefy falhar
                    print(f"[CHAT] ⚠️ Erro ao sincronizar com Pipefy (não crítico): {e}")

        want_slots = merged.interest_confirmed is True
        offered_slots = (resp.get("action") or {}).get("type") == "OFFER_SLOTS"

        print(f"[CHAT] want_slots={want_slots}, offered_slots={offered_slots}")

        if want_slots and not offered_slots:
            # 1) planeja janelas com base na frase do usuário
            rs, re, alvo_h, modo, fallbacks = plan_windows(body.message)
            print(f"[CHAT] janela principal (UTC): {rs} → {re} | modo={modo} alvo={alvo_h}")

            # 2) busca slots na janela principal e FILTRA pela janela em BRT
            print(f"[CHAT] Buscando slots no cal.com: {rs} → {re}")
            slots = get_slots(rs, re)
            print(f"[CHAT] Slots retornados do cal.com: {len(slots)}")
            if slots:
                print(f"[CHAT] Primeiros slots recebidos: {[{'id': s.get('id', '?'), 'start': s.get('start', '?')} for s in slots[:3]]}")
                print(f"[CHAT] Janela de filtro (BRT): {_to_brt(rs)} → {_to_brt(re)}")
            slots = filter_slots_by_window(slots, rs, re)
            print(f"[CHAT] Slots após filtro de janela: {len(slots)}")

            # 3) 'a partir de X' → garanta >= X em BRT
            if modo == "after" and alvo_h is not None:
                slots = clamp_after_hour(slots, alvo_h)
                print(f"[CHAT] Slots após clamp_after_hour (h >= {alvo_h}): {len(slots)}")

            # 4) fallbacks (mesma janela amanhã; depois dia inteiro, mas ainda filtra)
            i = 0
            while not slots and i < len(fallbacks):
                fs, fe = fallbacks[i]
                print(f"[CHAT] fallback {i+1}: {fs} → {fe}")
                print(f"[CHAT] Buscando slots no cal.com (fallback {i+1}): {fs} → {fe}")
                slots = get_slots(fs, fe)
                print(f"[CHAT] Slots retornados do cal.com (fallback {i+1}): {len(slots)}")
                slots = filter_slots_by_window(slots, fs, fe)
                print(f"[CHAT] Slots após filtro de janela (fallback {i+1}): {len(slots)}")
                if modo == "after" and alvo_h is not None:
                    slots = clamp_after_hour(slots, alvo_h)
                    print(f"[CHAT] Slots após clamp_after_hour (fallback {i+1}): {len(slots)}")
                i += 1

            # 5) prioriza por proximidade quando houver alvo_h
            slots = prioritize_slots(slots, alvo_h)

            # 6) limita a 5 (aumentado de 3 para dar mais opções quando há muitos slots disponíveis)
            slots = slots[:5]
            print(f"[CHAT] Total de slots após filtros e priorização: {len(slots)}")

            # Se não encontrou slots após filtros, tenta estratégias alternativas
            if not slots:
                print("[CHAT] ⚠️ Nenhum slot encontrado após busca e filtros, tentando estratégias alternativas")
                
                # Estratégia 1: Se o usuário especificou um dia específico, busca slots do mesmo dia sem restrição de hora
                base_brt, _ = parse_date_pt(body.message)
                if base_brt.date() != _today_brt().date():  # Se não é hoje
                    print(f"[CHAT] Buscando slots do dia solicitado ({base_brt.date()}) sem restrição de hora")
                    dia_inicio_utc = datetime.combine(base_brt.date(), time(0,0), tzinfo=BRT).astimezone(timezone.utc)
                    dia_fim_utc = datetime.combine(base_brt.date(), time(23,59,59), tzinfo=BRT).astimezone(timezone.utc)
                    alt_slots = get_slots(dia_inicio_utc, dia_fim_utc)
                    if alt_slots:
                        # Filtra apenas pela data, não pela hora
                        alt_slots = [s for s in alt_slots if _to_brt(datetime.fromisoformat(s["start"].replace("Z", "+00:00"))).date() == base_brt.date()]
                        if alt_slots:
                            alt_slots = sorted(alt_slots, key=lambda s: s.get("start", ""))[:5]
                            print(f"[CHAT] Encontrei {len(alt_slots)} slots do dia solicitado em outros horários")
                            slots = alt_slots
                
                # Estratégia 2: Se ainda não tem slots, busca nos próximos dias
                if not slots:
                    print("[CHAT] Buscando slots alternativos nos próximos dias")
                    from datetime import timedelta
                    tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    week_later_utc = tomorrow_utc + timedelta(days=7)
                    alt_slots = get_slots(tomorrow_utc, week_later_utc)
                    # Limita a 5 e ordena por data
                    if alt_slots:
                        alt_slots = sorted(alt_slots, key=lambda s: s.get("start", ""))[:5]
                        print(f"[CHAT] Encontrei {len(alt_slots)} slots alternativos para oferecer")
                        slots = alt_slots

            if not slots:
                print("[CHAT] ⚠️ Nenhum slot disponível em nenhum período")
                # Se não encontrou slots, informa ao usuário
                resp["reply"] = "Desculpe, não encontrei horários disponíveis no período solicitado. Você teria alguma outra preferência de dia e horário?"
                resp["action"] = {"type": "ASK"}
            else:
                # 7) reinvoca LLM para oferecer (sem inventar)
                # Verifica se os slots são do dia solicitado mas em horário diferente
                base_brt, _ = parse_date_pt(body.message)
                slots_date = None
                if slots:
                    first_slot_date = _to_brt(datetime.fromisoformat(slots[0]["start"].replace("Z", "+00:00"))).date()
                    slots_date = first_slot_date
                
                if modo == "after" and alvo_h is not None and slots_date == base_brt.date():
                    # Slots do mesmo dia mas em horário diferente - precisa informar
                    prompt = f"O usuário pediu horários após as {alvo_h}h do dia {base_brt.strftime('%d/%m')}, mas só temos disponibilidade em outros horários do mesmo dia. Ofereça estes horários explicando que são do dia solicitado mas em horários diferentes, e pergunte se algum deles funciona."
                else:
                    prompt = "Ofereça estes horários para o usuário, no mesmo idioma."
                
                print(f"[CHAT] Encontrei {len(slots)} slots, reinvocando LLM para oferecer")
                resp = llm.respond(build_state(slots=slots), prompt)
                act = resp.get("action") or {}
                if not act.get("type"):
                    act["type"] = "OFFER_SLOTS"
                act["slots"] = slots
                # Garante que o reply esteja no action quando há slots
                reply_text = act.get("reply") or resp.get("reply") or "Perfeito! Esses horários funcionam pra você?"
                act["reply"] = reply_text
                resp["action"] = act
                # Garante que reply no nível raiz também exista para compatibilidade
                if not resp.get("reply"):
                    resp["reply"] = reply_text
                print(f"[CHAT] Action configurado: type={act.get('type')}, slots={len(act.get('slots', []))}, reply={reply_text[:50]}...")
                print(f"[CHAT] Slots que serão enviados: {[s.get('start') for s in slots[:3]]}")

        # normaliza reply
        reply = resp.get("action", {}).get("reply") or resp.get("reply") or "Certo."

        # salva resposta do bot
        db.add(Message(session_id=body.sessionId, role="assistant", content=reply))
        db.commit()
        return resp
