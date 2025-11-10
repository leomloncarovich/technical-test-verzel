import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { getSessionId } from '../lib/session.js';
import { postChat, schedule } from '../lib/api.js';

type Msg = { who: 'user' | 'bot'; text: string; timestamp?: Date };
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
        return parsed.map((m: any) => ({
          ...m,
          timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
        }));
      }
    }
  } catch (e) {
  }
  return [];
}

function saveMessagesToCache(sessionId: string, messages: Msg[]): void {
  try {
    const key = getMessagesCacheKey(sessionId);
    const messagesToCache = messages.slice(-50).map(m => ({
      ...m,
      timestamp: m.timestamp?.toISOString(),
    }));
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

function formatTime(date: Date): string {
  return date.toLocaleTimeString('pt-BR', { 
    hour: '2-digit', 
    minute: '2-digit' 
  });
}

export default function Chat() {
  const [sessionId, setSessionId] = useState<string>(getSessionId);
  const [messages, setMessages] = useState<Msg[]>(() => {
    const initialSessionId = getSessionId();
    const cached = loadMessagesFromCache(initialSessionId);
    if (cached.length > 0) {
      return cached;
    }
    return [{ 
      who: 'bot', 
      text: 'Olá! Sou seu assistente de pré-vendas. Como posso ajudar?',
      timestamp: new Date(),
    }];
  });
  const [input, setInput] = useState('');
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [focusedSlotIndex, setFocusedSlotIndex] = useState<number>(-1);
  const scroller = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const slotRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    saveMessagesToCache(sessionId, messages);
  }, [messages, sessionId]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' });
  }, [messages, slots]);

  useEffect(() => {
    if (!slots && focusedSlotIndex >= 0) {
      setFocusedSlotIndex(-1);
      inputRef.current?.focus();
    }
  }, [slots, focusedSlotIndex]);

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
    const userMsg: Msg = { who: 'user', text, timestamp: new Date() };
    setMessages(m => [...m, userMsg]);
    setLoading(true);
    try {
      const resp: any = await postChat(text, sessionId);
      
      if (resp?.action?.type === 'SESSION_EXPIRED') {
        clearMessagesCache(sessionId);
        setMessages([{ 
          who: 'bot', 
          text: resp.reply || 'Sua sessão expirou por inatividade. Por favor, recarregue a página para iniciar uma nova conversa.',
          timestamp: new Date(),
        }]);
        setSlots(null);
        return;
      }
      
      const reply = resp?.action?.reply ?? resp?.reply ?? 'Certo!';
      const botMsg: Msg = { who: 'bot', text: reply, timestamp: new Date() };
      setMessages(m => [...m, botMsg]);
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
      setMessages(m => [...m, { 
        who: 'bot', 
        text: 'Falha ao processar. Tente novamente.',
        timestamp: new Date(),
      }]);
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
      setMessages(m => [...m, { 
        who: 'bot', 
        text: `Reunião marcada! Link: ${data.meetingLink}`,
        timestamp: new Date(),
      }]);
      setSlots(null);
    } catch {
      setMessages(m => [...m, { 
        who: 'bot', 
        text: 'Não consegui marcar. Tente outro horário.',
        timestamp: new Date(),
      }]);
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
    <div className="flex flex-col w-full max-w-2xl mx-auto bg-white dark:bg-gray-800 rounded-xl sm:rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden min-h-[500px] sm:min-h-[600px] max-h-[75vh] sm:max-h-[85vh]">
      {/* Header do Chat */}
      <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 md:px-6 py-3 sm:py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
        <div className="shrink-0">
          <div className="w-9 h-9 sm:w-10 sm:h-10 md:w-12 md:h-12 rounded-full bg-gradient-to-br from-sky-400 to-cyan-500 flex items-center justify-center">
            <svg 
              className="w-5 h-5 sm:w-6 sm:h-6 md:w-7 md:h-7 text-white" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
              aria-hidden="true"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" 
              />
            </svg>
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 sm:gap-2">
            <h2 className="text-sm sm:text-base md:text-lg font-semibold text-gray-900 dark:text-white">
              SDR Agent
            </h2>
            <span 
              className="shrink-0 w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-green-500"
              aria-label="Online"
            />
          </div>
          <p className="text-[10px] sm:text-xs md:text-sm text-gray-500 dark:text-gray-400 truncate">
            Online • Responde em segundos
          </p>
        </div>
      </div>

      {/* Área de Mensagens */}
      <div
        ref={scroller}
        role="log"
        aria-live="polite"
        aria-label="Histórico de mensagens do chat"
        className="flex-1 overflow-y-auto px-3 sm:px-4 md:px-6 py-4 sm:py-5 md:py-6 space-y-3 sm:space-y-4 bg-gray-50 dark:bg-gray-900/30"
      >
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex gap-3 ${m.who === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
            role={m.who === 'bot' ? 'status' : undefined}
          >
            {m.who === 'bot' && (
              <div className="shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-gradient-to-br from-sky-400 to-cyan-500 flex items-center justify-center">
                <svg 
                  className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" 
                  fill="none" 
                  viewBox="0 0 24 24" 
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path 
                    strokeLinecap="round" 
                    strokeLinejoin="round" 
                    strokeWidth={2} 
                    d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" 
                  />
                </svg>
              </div>
            )}
            <div className={`flex flex-col max-w-[80%] sm:max-w-[75%] md:max-w-[80%] ${m.who === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`px-3 py-2 sm:px-4 sm:py-2.5 rounded-xl sm:rounded-2xl ${
                  m.who === 'bot'
                    ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 shadow-sm'
                    : 'bg-gradient-to-br from-sky-500 to-cyan-600 text-white shadow-md'
                }`}
                aria-label={m.who === 'bot' ? 'Mensagem do assistente' : 'Sua mensagem'}
              >
                <p className="text-xs sm:text-sm md:text-base leading-relaxed whitespace-pre-wrap break-words">
                  {m.text}
                </p>
              </div>
              {m.timestamp && (
                <span 
                  className={`text-xs text-gray-400 dark:text-gray-500 mt-1 ${m.who === 'user' ? 'text-right' : 'text-left'}`}
                  aria-label={`Enviado às ${formatTime(m.timestamp)}`}
                >
                  {formatTime(m.timestamp)}
                </span>
              )}
            </div>
            {m.who === 'user' && (
              <div className="shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-gradient-to-br from-gray-400 to-gray-500 flex items-center justify-center">
                <svg 
                  className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" 
                  fill="none" 
                  viewBox="0 0 24 24" 
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path 
                    strokeLinecap="round" 
                    strokeLinejoin="round" 
                    strokeWidth={2} 
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" 
                  />
                </svg>
              </div>
            )}
          </div>
        ))}
        
        {slots && slots.length > 0 && (
          <div
            className="flex flex-col gap-2 my-4"
            role="group"
            aria-label="Horários disponíveis para agendamento"
          >
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 px-1">
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
                className="px-4 py-3 text-left border-2 border-sky-400 dark:border-sky-500 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 hover:bg-sky-50 dark:hover:bg-sky-900/20 hover:border-sky-500 dark:hover:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 transition-all"
                aria-label={`Agendar reunião para ${formatSlotTime(s.start, s.end)}`}
                tabIndex={focusedSlotIndex === index ? 0 : -1}
              >
                <span className="text-sm sm:text-base font-medium">
                  {formatSlotTime(s.start, s.end)}
                </span>
              </button>
            ))}
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 px-1">
              Use as setas ↑↓ para navegar, Enter para selecionar, Esc para cancelar
            </p>
          </div>
        )}
        
        {loading && (
          <div className="flex gap-2 sm:gap-3">
            <div className="shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-gradient-to-br from-sky-400 to-cyan-500 flex items-center justify-center">
              <svg 
                className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" 
                fill="none" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
                aria-hidden="true"
              >
                <path 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                  strokeWidth={2} 
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" 
                />
              </svg>
            </div>
            <div className="px-4 py-2.5 rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Input Area */}
      <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3 sm:p-4">
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
            className="flex-1 px-3 py-2.5 sm:px-4 sm:py-3 text-sm sm:text-base rounded-lg sm:rounded-xl border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Enviar mensagem"
            className="px-3 py-2.5 sm:px-4 sm:py-3 rounded-lg sm:rounded-xl bg-gradient-to-br from-sky-500 to-cyan-600 text-white font-medium hover:from-sky-600 hover:to-cyan-700 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg flex items-center justify-center min-w-[44px] sm:min-w-[48px]"
          >
            <svg 
              className="w-4 h-4 sm:w-5 sm:h-5" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
              aria-hidden="true"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" 
              />
            </svg>
          </button>
        </form>
        <p id="input-help" className="sr-only">
          Pressione Enter para enviar ou Esc para cancelar seleção de horários
        </p>
      </div>
    </div>
  );
}
