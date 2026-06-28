import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getToken, ai } from '../api';
import Sidebar from '../components/Sidebar';

export default function QaHomePage() {
  const nav = useNavigate();
  const textareaRef = useRef(null);

  const [question, setQuestion] = useState('');
  const [count, setCount] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [sessions, setSessions] = useState([]);

  const loadSessions = useCallback(() => {
    ai.sessions().then(setSessions).catch(() => {});
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // Auto-resize textarea
  const autoResize = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 240) + 'px';
  };

  // Submit question → POST → navigate to session page
  const submit = async () => {
    const q = question.trim();
    if (!q || submitting) return;
    setSubmitting(true);
    setError('');

    try {
      const res = await fetch('/api/ai/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ question: q, count }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      // Read just the first SSE message to get session_id
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let sid = null;

      while (!sid) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const msg = JSON.parse(line.slice(6));
              if (msg.event === 'session') {
                sid = msg.data.session_id;
                break;
              }
            } catch {}
          }
        }
      }

      // Cancel the rest — SessionPage will re-poll or detect running
      try { reader.cancel(); } catch {}

      if (sid) {
        nav(`/session/${sid}`, { state: { streaming: true, count } });
      } else {
        throw new Error('Failed to get session ID');
      }
    } catch (e) {
      setError(e.message || 'Something went wrong');
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        sessions={sessions}
        activeId={null}
        onSelect={(id) => nav(`/session/${id}`)}
        onRefresh={loadSessions}
      />
      <main className="main-content">
        <div className="home-center">
          <h1 className="home-title">QA</h1>
          <p className="home-subtitle">Math AI Assistant</p>

          <div className="home-input-area">
            <textarea
              ref={textareaRef}
              value={question}
              onChange={e => { setQuestion(e.target.value); autoResize(); }}
              onKeyDown={handleKeyDown}
              placeholder="Ask a mathematical question…"
              rows={3}
              disabled={submitting}
              autoFocus
            />
            {error && <div className="home-error">{error}</div>}
            <div className="home-controls">
              <select value={count} onChange={e => setCount(+e.target.value)} disabled={submitting}>
                {[1,2,3,4,5,6,7,8].map(n => (
                  <option key={n} value={n}>{n} {n === 1 ? 'answer' : 'answers'}</option>
                ))}
              </select>
              <button onClick={submit} disabled={submitting || !question.trim()}>
                {submitting ? 'Sending…' : 'Send'}
              </button>
              <span className="home-hint">⌘/Ctrl + Enter</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
