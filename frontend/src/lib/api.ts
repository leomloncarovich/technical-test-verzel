// frontend/src/lib/api.ts
// Em produção, usa URL relativa. Em desenvolvimento, usa a variável de ambiente ou localhost
const API_BASE = import.meta.env.VITE_API_BASE_URL || 
  (import.meta.env.PROD ? '' : 'http://localhost:8000');

export async function postChat(message: string, sessionId: string) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, sessionId })
  });
  if (!res.ok) throw new Error('Chat request failed');
  return res.json();
}

type ScheduleOpts = {
  startIso?: string;
  endIso?: string;
  attendeeName?: string;
  attendeeEmail?: string;
};

export async function schedule(slotId: string, sessionId: string, opts?: ScheduleOpts) {
  const res = await fetch(`${API_BASE}/api/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      slotId,
      sessionId,
      ...(opts || {}) // <- inclui startIso/endIso/attendee*
    })
  });
  if (!res.ok) throw new Error('Schedule request failed');
  return res.json();
}
