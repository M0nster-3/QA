import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getToken, ai } from '../api';
import Sidebar from '../components/Sidebar';
import CopyButton from '../components/CopyButton';
import MarkdownRenderer from '../components/MarkdownRenderer';
import useSSE from '../hooks/useSSE';

/* ── Time formatting ──────────────────────────────────── */

function formatGenTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return isoStr;
  return d.toLocaleString([], {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

/* ── SessionPage ──────────────────────────────────────── */

export default function SessionPage() {
  const { sessionId } = useParams();
  const nav = useNavigate();

  const [session, setSession] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSlot, setActiveSlot] = useState(1);
  const [thinkingOpen, setThinkingOpen] = useState(false);

  const pollingRef = useRef(null);
  const mountedRef = useRef(true);

  // SSE for regenerate
  const sse = useSSE();

  // Load session list
  const loadSessions = useCallback(() => {
    ai.sessions().then(setSessions).catch(() => {});
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // ── Determine if session has incomplete slots ──────
  const hasIncompleteSlots = useCallback((data) => {
    if (!data) return false;
    const completedSlots = new Set(
      (data.answers || [])
        .filter(a => a.generated_at)
        .map(a => a.slot)
    );
    const totalExpected = data.answer_count || data.count || 1;
    return completedSlots.size < totalExpected;
  }, []);

  // ── Poll for session detail ────────────────────────
  const startPolling = useCallback((id) => {
    if (pollingRef.current) clearTimeout(pollingRef.current);
    let failCount = 0;

    const poll = async () => {
      if (!mountedRef.current) return;
      try {
        const data = await ai.sessionDetail(id);
        if (!mountedRef.current) return;
        failCount = 0;
        setSession(data);
        if (hasIncompleteSlots(data)) {
          pollingRef.current = setTimeout(poll, 3000);
        } else {
          loadSessions();
        }
      } catch {
        failCount++;
        if (mountedRef.current && failCount < 5) {
          pollingRef.current = setTimeout(poll, 5000);
        }
      }
    };
    poll();
  }, [hasIncompleteSlots, loadSessions]);

  // ── Initial load ───────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    setSession(null);
    setActiveSlot(1);
    setThinkingOpen(false);
    sse.setSlots({});
    sse.setSessionId(null);
    startPolling(sessionId);

    return () => {
      mountedRef.current = false;
      if (pollingRef.current) clearTimeout(pollingRef.current);
      sse.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // ── Regenerate a slot ──────────────────────────────
  const regenerate = async (slot) => {
    sse.resetSlot(slot);
    setActiveSlot(slot);

    await sse.startStream(`/api/ai/sessions/${sessionId}/regenerate/${slot}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    startPolling(sessionId);
    loadSessions();
  };

  // ── Build slot data ────────────────────────────────
  const completedBySlot = {};
  if (session?.answers) {
    for (const a of session.answers) completedBySlot[a.slot] = a;
  }

  const getSlotData = (slot) => {
    if (sse.slots[slot] && !sse.slots[slot].done) return sse.slots[slot];
    if (sse.slots[slot]?.done && sse.slots[slot]?.answer) return sse.slots[slot];
    return completedBySlot[slot] || null;
  };

  const totalSlots = session?.answer_count || session?.count || 1;
  const activeData = getSlotData(activeSlot);
  const isSlotComplete = (slot) => {
    const d = completedBySlot[slot];
    return d && d.generated_at;
  };
  const isSlotRunning = (slot) => {
    if (sse.slots[slot] && !sse.slots[slot].done) return true;
    return session?.running_slots?.includes(slot) || false;
  };
  const allComplete = session && !hasIncompleteSlots(session) && !sse.isStreaming;

  // ── Loading state ──────────────────────────────────
  if (!session) {
    return (
      <div className="app-layout">
        <Sidebar
          sessions={sessions}
          activeId={Number(sessionId)}
          onSelect={(id) => nav(`/session/${id}`)}
          onRefresh={loadSessions}
        />
        <main className="main-content">
          <div className="session-loading">Loading session…</div>
        </main>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────
  return (
    <div className="app-layout">
      <Sidebar
        sessions={sessions}
        activeId={Number(sessionId)}
        onSelect={(id) => nav(`/session/${id}`)}
        onRefresh={loadSessions}
      />
      <main className="main-content">
        <div className="session-container">

          {/* Question header */}
          <div className="session-header">
            <p className="session-question"><strong>Q:</strong> {session.question}</p>
            <p className="session-meta">
              {totalSlots} {totalSlots === 1 ? 'answer' : 'answers'}
              {' · '}
              {formatGenTime(session.created_at)}
              {!allComplete && <span className="running-badge"> ⏳ Running…</span>}
            </p>
          </div>

          {/* Slot tabs (only if multiple) */}
          {totalSlots > 1 && (
            <div className="slot-tabs">
              {Array.from({ length: totalSlots }, (_, i) => i + 1).map(slot => {
                const complete = isSlotComplete(slot);
                const running = isSlotRunning(slot);
                return (
                  <button
                    key={slot}
                    className={`slot-tab${slot === activeSlot ? ' active' : ''}${complete ? ' done' : ''}${running ? ' running' : ''}`}
                    onClick={() => { setActiveSlot(slot); setThinkingOpen(false); }}
                  >
                    Answer {slot} {complete && !running ? '✓' : running ? '⏳' : ''}
                  </button>
                );
              })}
            </div>
          )}

          {/* Active slot content */}
          <div className="slot-content">
            {activeData ? (
              <>
                {/* Thinking block */}
                {activeData.thinking && (
                  <div className="thinking-block">
                    <div className="block-header">
                      <span className="toggle" onClick={() => setThinkingOpen(!thinkingOpen)}>
                        {thinkingOpen ? '▾' : '▸'} Thinking
                        {isSlotRunning(activeSlot) && !activeData.answer && !thinkingOpen && (
                          <span className="spinner"> ⏳</span>
                        )}
                      </span>
                      <CopyButton text={activeData.thinking} />
                    </div>
                    {thinkingOpen && (
                      <div className="thinking-body">
                        <MarkdownRenderer content={activeData.thinking} />
                      </div>
                    )}
                  </div>
                )}

                {/* Answer block */}
                <div className="answer-block">
                  <div className="block-header">
                    <span>{totalSlots === 1 ? 'Answer' : `Answer ${activeSlot}`}</span>
                    <div className="header-actions">
                      {(isSlotComplete(activeSlot) || activeData.done) &&
                       !isSlotRunning(activeSlot) && (
                        <button className="btn-regen" onClick={() => regenerate(activeSlot)}>
                          ↻ Regenerate
                        </button>
                      )}
                      <CopyButton text={activeData.answer} />
                    </div>
                  </div>
                  <div className="answer-body">
                    {activeData.answer ? (
                      <MarkdownRenderer content={activeData.answer} />
                    ) : isSlotRunning(activeSlot) ? (
                      <p className="gen-msg"><span className="spinner">⏳</span> Generating answer…</p>
                    ) : (
                      <p className="gen-msg">Waiting…</p>
                    )}
                    {/* 续写进度指示 */}
                    {isSlotRunning(activeSlot) && activeData?.continuation > 0 && (
                      <p className="continuation-badge">
                        🔄 Continuation {activeData.continuation}/{20}
                        {activeData.maxContinuation && ' — max reached'}
                      </p>
                    )}
                  </div>
                </div>

                {/* Generation time */}
                {activeData.generated_at && (
                  <p className="gen-time">Generated: {formatGenTime(activeData.generated_at)}</p>
                )}
              </>
            ) : isSlotRunning(activeSlot) ? (
              <p className="gen-msg"><span className="spinner">⏳</span> This answer is being generated…</p>
            ) : (
              <p className="gen-msg">No answer yet for this slot.</p>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}
