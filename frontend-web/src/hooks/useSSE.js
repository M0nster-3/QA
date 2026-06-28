import { useState, useRef, useCallback } from 'react';

/* ── SSE parsing helpers ──────────────────────────────── */

function parseSSE(buffer) {
  const messages = [];
  const lines = buffer.split('\n');
  const remaining = lines.pop() || '';
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      try { messages.push(JSON.parse(line.slice(6))); } catch {}
    }
  }
  return { messages, remaining };
}

function parseSlotFromEvent(event) {
  const m = event.match(/^slot_(\d+)_(\w+)$/);
  if (!m) return null;
  return { slot: parseInt(m[1]), type: m[2] };
}

/* ── Hook ─────────────────────────────────────────────── */

export default function useSSE() {
  const [slots, setSlots] = useState({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const abortRef = useRef(null);

  const consumeStream = useCallback(async (response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const { messages, remaining } = parseSSE(buffer);
        buffer = remaining;
        for (const msg of messages) {
          if (msg.event === 'session') {
            setSessionId(msg.data.session_id);
            continue;
          }
          const parsed = parseSlotFromEvent(msg.event);
          if (!parsed) continue;
          const { slot, type } = parsed;
          if (type === 'thinking') {
            setSlots(prev => ({
              ...prev,
              [slot]: { ...prev[slot], thinking: (prev[slot]?.thinking || '') + (msg.data.token || '') },
            }));
          } else if (type === 'answer') {
            setSlots(prev => ({
              ...prev,
              [slot]: { ...prev[slot], answer: (prev[slot]?.answer || '') + (msg.data.token || '') },
            }));
          } else if (type === 'done') {
            setSlots(prev => ({
              ...prev,
              [slot]: { ...prev[slot], done: true },
            }));
          } else if (type === 'error') {
            setSlots(prev => ({
              ...prev,
              [slot]: { ...prev[slot], done: true, error: msg.data.error || 'Unknown error' },
            }));
          } else if (type === 'continuation') {
            setSlots(prev => ({
              ...prev,
              [slot]: { ...prev[slot], continuation: msg.data.iteration || 1 },
            }));
          } else if (type === 'max_cont') {
            setSlots(prev => ({
              ...prev,
              [slot]: { ...prev[slot], maxContinuation: true },
            }));
          }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') return;
      console.error('SSE stream error:', e);
    } finally {
      try { reader.cancel(); } catch {}
    }
  }, []);

  const startStream = useCallback(async (url, { method = 'POST', headers = {}, body } = {}) => {
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setIsStreaming(true);

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', ...headers },
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await consumeStream(res);
    } catch (e) {
      if (e.name !== 'AbortError') console.error('Stream fetch error:', e);
    } finally {
      setIsStreaming(false);
    }
  }, [consumeStream]);

  const initSlots = useCallback((count) => {
    const initial = {};
    for (let i = 1; i <= count; i++) initial[i] = { thinking: '', answer: '', done: false };
    setSlots(initial);
  }, []);

  const resetSlot = useCallback((slot) => {
    setSlots(prev => ({
      ...prev,
      [slot]: { thinking: '', answer: '', done: false },
    }));
  }, []);

  const abort = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
  }, []);

  return {
    slots,
    setSlots,
    isStreaming,
    sessionId,
    setSessionId,
    startStream,
    initSlots,
    resetSlot,
    abort,
  };
}
