import { useEffect, useRef, useState } from 'react';
import { getSessionId } from '../lib/session.js';
import { postChat, schedule } from '../lib/api.js';

type Msg = { who: 'user' | 'bot'; text: string };
type Slot = { id: string; start: string; end: string };

const MESSAGES_CACHE_KEY_PREFIX = 'sdr_messages_';

function getMessagesCacheKey(sessionId: string): string {
  return `${MESSAGES_CACHE_KEY_PREFIX}${sessionId}`;
}

function loadMessagesFromCache(sessionId: string): Msg[] {
  try {
    const key = getMessagesCacheKey(sessionId);
    const cached = localStorage.getItem(key);
    if (cached) {
      const parsed = JSON.parse(cached);
      // Valida que é um array de mensagens válidas
      if (Array.isArray(parsed) && parsed.every((m: any) => m.who && m.text)) {
        return parsed;
      }
    }
  } catch (e) {
  }
  return [];
}

function saveMessagesToCache(sessionId: string, messages: Msg[]): void {
  try {
    const key = getMessagesCacheKey(sessionId);
    // Limita a 50 mensagens no cache local para não exceder limites do localStorage
    const messagesToCache = messages.slice(-50);
    localStorage.setItem(key, JSON.stringify(messagesToCache));
  } catch (e) {
  }
}

function clearMessagesCache(sessionId: string): void {
  try {
    const key = getMessagesCacheKey(sessionId);
    localStorage.removeItem(key);
  } catch (e) {
  }
}

export default function Chat() {
  const [sessionId, setSessionId] = useState<string>(getSessionId);
  const [messages, setMessages] = useState<Msg[]>(() => {
    // Tenta carregar do cache, senão usa mensagem inicial
    const initialSessionId = getSessionId();
    const cached = loadMessagesFromCache(initialSessionId);
    if (cached.length > 0) {
      return cached;
    }
    return [{ who: 'bot', text: 'Olá! Sou seu assistente de pré-vendas. Como posso ajudar?' }];
  });
  const [input, setInput] = useState('');
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [loading, setLoading] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  // Salva mensagens no cache sempre que mudarem
  useEffect(() => {
    saveMessagesToCache(sessionId, messages);
  }, [messages, sessionId]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
  }, [messages, slots]);

  async function send(text: string) {
    if (!text.trim()) return;
    setMessages(m => [...m, { who: 'user', text }]);
    setLoading(true);
    try {
      const resp: any = await postChat(text, sessionId);
      
      // Verifica se a sessão expirou
      if (resp?.action?.type === 'SESSION_EXPIRED') {
        // Limpa o cache quando a sessão expira
        clearMessagesCache(sessionId);
        setMessages([{ who: 'bot', text: resp.reply || 'Sua sessão expirou por inatividade. Por favor, recarregue a página para iniciar uma nova conversa.' }]);
        setSlots(null);
        return;
      }
      
      const reply = resp?.action?.reply ?? resp?.reply ?? 'Certo!';
      setMessages(m => [...m, { who: 'bot', text: reply }]);
      if (resp?.action?.type === 'OFFER_SLOTS') setSlots(resp.action.slots);
      else if (resp?.action?.type === 'CONFIRM_SCHEDULE') setSlots(null);
      else setSlots(null);
      
      // Atualiza sessionId se o backend retornou um novo
      if (resp?.sessionId && resp.sessionId !== sessionId) {
        // Migra mensagens do cache antigo para o novo sessionId ANTES de atualizar o state
        const currentMessages = messages; // Usa o state atual que já tem as novas mensagens
        if (currentMessages.length > 0) {
          saveMessagesToCache(resp.sessionId, currentMessages);
        }
        // Limpa o cache do sessionId antigo
        clearMessagesCache(sessionId);
        // Atualiza sessionId no state e no localStorage
        setSessionId(resp.sessionId);
        localStorage.setItem('sdr_session_id', resp.sessionId);
      }
    } catch (e) {
      setMessages(m => [...m, { who: 'bot', text: 'Falha ao processar. Tente novamente.' }]);
    } finally {
      setLoading(false);
    }
  }

  async function onPickSlot(slotId: string, start?: string, end?: string) {
    setLoading(true);
    try {
      const data = await schedule(slotId, sessionId, {
        startIso: start,
        endIso: end,
        attendeeEmail: 'lead@example.com',
      });
      setMessages(m => [...m, { who: 'bot', text: `Reunião marcada! Link: ${data.meetingLink}` }]);
      setSlots(null);
    } catch {
      setMessages(m => [...m, { who: 'bot', text: 'Não consegui marcar. Tente outro horário.' }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat">
      <div className="messages" ref={scroller} role="log" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={m.who === 'bot' ? 'msg bot' : 'msg user'}>
            {m.text}
          </div>
        ))}
        {slots && (
          <div className="slots">
            {slots.map(s => (
              <button key={s.id} onClick={() => onPickSlot(s.id, s.start, s.end)}>
                {new Date(s.start).toLocaleString()} - {new Date(s.end).toLocaleTimeString()}
              </button>
            ))}
          </div>
        )}
        {loading && <div className="msg bot">...</div>}
      </div>
      <form
        onSubmit={e => {
          e.preventDefault();
          const v = input;
          setInput('');
          send(v);
        }}
      >
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Digite sua mensagem..."
          aria-label="Mensagem"
        />
        <button type="submit">Enviar</button>
      </form>
      <style>{`
        .chat { max-width: 640px; margin: 0 auto; padding: 16px; display:flex; flex-direction:column; height: 100vh; box-sizing: border-box; }
        .messages { flex:1; overflow:auto; border: 1px solid #ddd; border-radius: 8px; padding: 8px; }
        .msg { padding: 8px 12px; border-radius: 12px; margin: 6px 0; max-width: 85%; }
        .msg.bot { background:rgb(63, 63, 255); }
        .msg.user { background: #0000ff; align-self: flex-end; }
        form { display:flex; gap:8px; margin-top: 8px; }
        input { flex:1; padding: 10px; border-radius: 8px; border: 1px solid #ccc; }
        button { padding: 10px 14px; border-radius: 8px; border: 1px solid #ccc; cursor:pointer; }
        .slots { display:flex; flex-direction: column; gap: 8px; margin: 8px 0; }
        @media (max-width: 480px){ .chat{ padding: 8px; } }
      `}</style>
    </div>
  );
}
