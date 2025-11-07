import { useEffect, useRef, useState } from 'react';
import { getSessionId } from '../lib/session';
import { postChat, schedule } from '../lib/api';

type Msg = { who: 'user' | 'bot'; text: string };
type Slot = { id: string; start: string; end: string };

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([
    { who: 'bot', text: 'Olá! Sou seu assistente de pré-vendas. Como posso ajudar?' }
  ]);
  const [input, setInput] = useState('');
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [loading, setLoading] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const sessionId = getSessionId();

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
  }, [messages, slots]);

  async function send(text: string) {
    if (!text.trim()) return;
    setMessages(m => [...m, { who: 'user', text }]);
    setLoading(true);
    try {
      const resp: any = await postChat(text, sessionId);
      console.log(resp);
      const reply = resp?.action?.reply ?? resp?.reply ?? 'Certo!';
      setMessages(m => [...m, { who: 'bot', text: reply }]);
      if (resp?.action?.type === 'OFFER_SLOTS') setSlots(resp.action.slots);
      else if (resp?.action?.type === 'CONFIRM_SCHEDULE') setSlots(null);
      else setSlots(null);
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
