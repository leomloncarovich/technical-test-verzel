import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
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
  const [focusedSlotIndex, setFocusedSlotIndex] = useState<number>(-1);
  const scroller = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const slotRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Salva mensagens no cache sempre que mudarem
  useEffect(() => {
    saveMessagesToCache(sessionId, messages);
  }, [messages, sessionId]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
  }, [messages, slots]);

  // Foca no input quando slots são limpos
  useEffect(() => {
    if (!slots && focusedSlotIndex >= 0) {
      setFocusedSlotIndex(-1);
      inputRef.current?.focus();
    }
  }, [slots, focusedSlotIndex]);

  // Foca no primeiro slot quando slots aparecem
  useEffect(() => {
    if (slots && slots.length > 0 && focusedSlotIndex === -1) {
      setFocusedSlotIndex(0);
      setTimeout(() => {
        slotRefs.current[0]?.focus();
      }, 100);
    }
  }, [slots]);

  async function send(text: string) {
    if (!text.trim()) return;
    setMessages(m => [...m, { who: 'user', text }]);
    setLoading(true);
    try {
      const resp: any = await postChat(text, sessionId);
      
      if (resp?.action?.type === 'SESSION_EXPIRED') {
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
      
      if (resp?.sessionId && resp.sessionId !== sessionId) {
        const currentMessages = messages;
        if (currentMessages.length > 0) {
          saveMessagesToCache(resp.sessionId, currentMessages);
        }
        clearMessagesCache(sessionId);
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
      });
      setMessages(m => [...m, { who: 'bot', text: `Reunião marcada! Link: ${data.meetingLink}` }]);
      setSlots(null);
    } catch {
      setMessages(m => [...m, { who: 'bot', text: 'Não consegui marcar. Tente outro horário.' }]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      if (slots) {
        setSlots(null);
        inputRef.current?.focus();
      }
    }
  }

  function handleSlotKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!slots) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        const nextIndex = index < slots.length - 1 ? index + 1 : 0;
        setFocusedSlotIndex(nextIndex);
        slotRefs.current[nextIndex]?.focus();
        break;
      case 'ArrowUp':
        e.preventDefault();
        const prevIndex = index > 0 ? index - 1 : slots.length - 1;
        setFocusedSlotIndex(prevIndex);
        slotRefs.current[prevIndex]?.focus();
        break;
      case 'Home':
        e.preventDefault();
        setFocusedSlotIndex(0);
        slotRefs.current[0]?.focus();
        break;
      case 'End':
        e.preventDefault();
        const lastIndex = slots.length - 1;
        setFocusedSlotIndex(lastIndex);
        slotRefs.current[lastIndex]?.focus();
        break;
      case 'Escape':
        e.preventDefault();
        setSlots(null);
        inputRef.current?.focus();
        break;
      case 'Tab':
        if (e.shiftKey && index === 0) {
          e.preventDefault();
          inputRef.current?.focus();
        }
        break;
    }
  }

  function formatSlotTime(start: string, end: string): string {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const dateStr = startDate.toLocaleDateString('pt-BR', { 
      day: '2-digit', 
      month: '2-digit', 
      year: 'numeric' 
    });
    const startTime = startDate.toLocaleTimeString('pt-BR', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
    const endTime = endDate.toLocaleTimeString('pt-BR', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
    return `${dateStr} das ${startTime} às ${endTime}`;
  }

  return (
    <div className="flex flex-col max-w-2xl mx-auto p-4 h-screen box-border">
      <div
        ref={scroller}
        role="log"
        aria-live="polite"
        aria-label="Histórico de mensagens do chat"
        className="flex-1 overflow-y-auto border border-gray-300 dark:border-gray-600 rounded-lg p-4 mb-4 bg-white dark:bg-gray-800"
      >
        {messages.map((m, i) => (
          <div
            key={i}
            className={`p-3 rounded-xl mb-3 max-w-[85%] ${
              m.who === 'bot'
                ? 'bg-blue-600 text-white self-start'
                : 'bg-blue-500 text-white self-end ml-auto'
            }`}
            role={m.who === 'bot' ? 'status' : undefined}
            aria-label={m.who === 'bot' ? 'Mensagem do assistente' : 'Sua mensagem'}
          >
            {m.text}
          </div>
        ))}
        
        {slots && slots.length > 0 && (
          <div
            className="flex flex-col gap-2 my-4"
            role="group"
            aria-label="Horários disponíveis para agendamento"
          >
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Selecione um horário disponível:
            </p>
            {slots.map((s, index) => (
              <button
                key={s.id}
                ref={(el) => {
                  slotRefs.current[index] = el;
                }}
                onClick={() => onPickSlot(s.id, s.start, s.end)}
                onKeyDown={(e) => handleSlotKeyDown(e, index)}
                className="px-4 py-3 text-left border-2 border-blue-500 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 hover:bg-blue-50 dark:hover:bg-blue-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                aria-label={`Agendar reunião para ${formatSlotTime(s.start, s.end)}`}
                tabIndex={focusedSlotIndex === index ? 0 : -1}
              >
                {formatSlotTime(s.start, s.end)}
              </button>
            ))}
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              Use as setas ↑↓ para navegar, Enter para selecionar, Esc para cancelar
            </p>
          </div>
        )}
        
        {loading && (
          <div
            className="p-3 rounded-xl mb-3 max-w-[85%] bg-blue-600 text-white self-start"
            role="status"
            aria-live="polite"
            aria-label="Processando"
          >
            ...
          </div>
        )}
      </div>
      
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const v = input;
          setInput('');
          send(v);
        }}
        className="flex gap-2"
        aria-label="Formulário de envio de mensagem"
      >
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Digite sua mensagem..."
          aria-label="Campo de texto para digitar sua mensagem"
          aria-describedby="input-help"
          disabled={loading}
          className="flex-1 px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          aria-label="Enviar mensagem"
          className="px-6 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Enviar
        </button>
      </form>
      <p id="input-help" className="sr-only">
        Pressione Enter para enviar ou Esc para cancelar seleção de horários
      </p>
    </div>
  );
}
