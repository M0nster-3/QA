import { useState, useEffect, useRef } from 'react';
import { ai } from '../api';

/* ── Time formatting ──────────────────────────────────── */

function formatTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return isoStr;

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const dateOnly = new Date(d.getFullYear(), d.getMonth(), d.getDate());

  if (dateOnly.getTime() === today.getTime()) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  if (dateOnly.getTime() === yesterday.getTime()) {
    return 'Yesterday';
  }
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
}

/* ── Sidebar ──────────────────────────────────────────── */

export default function Sidebar({ sessions, activeId, onSelect, onRefresh }) {
  const [menuOpen, setMenuOpen] = useState(null);
  const [delConfirm, setDelConfirm] = useState(null);
  const menuRef = useRef(null);

  // Close menu on outside click
  useEffect(() => {
    if (menuOpen === null) return;
    const close = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(null);
        setDelConfirm(null);
      }
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [menuOpen]);

  const handlePin = async (id) => {
    setMenuOpen(null);
    try {
      await ai.pinSession(id);
      onRefresh();
    } catch {}
  };

  const handleDelete = async (id) => {
    try {
      await ai.hideSession(id);
      onRefresh();
    } catch {}
    setMenuOpen(null);
    setDelConfirm(null);
  };

  const pinned = sessions.filter(s => s.pinned);
  const recent = sessions.filter(s => !s.pinned);

  const renderItem = (s) => {
    const isActive = s.session_id === activeId;
    const isMenuTarget = menuOpen === s.session_id;

    return (
      <div
        key={s.session_id}
        className={`session-item${isActive ? ' active' : ''}${s.pinned ? ' pinned' : ''}`}
        onClick={() => onSelect(s.session_id)}
      >
        <div className="session-item-row">
          <span className="session-item-q">
            {s.running && <span className="item-running">⏳ </span>}
            {s.question.slice(0, 55)}{s.question.length > 55 ? '…' : ''}
          </span>
          <button
            className="session-item-menu"
            onClick={e => {
              e.stopPropagation();
              setMenuOpen(isMenuTarget ? null : s.session_id);
              setDelConfirm(null);
            }}
          >⋯</button>
        </div>
        <div className="session-item-meta">
          {s.answer_count} {s.answer_count === 1 ? 'answer' : 'answers'} · {formatTime(s.created_at)}
        </div>

        {isMenuTarget && (
          <div
            className="session-item-dropdown"
            ref={menuRef}
            onClick={e => e.stopPropagation()}
          >
            {delConfirm === s.session_id ? (
              <div className="del-confirm">
                <span>Delete?</span>
                <button className="del-yes" onClick={() => handleDelete(s.session_id)}>Yes</button>
                <button className="del-no" onClick={() => { setDelConfirm(null); setMenuOpen(null); }}>No</button>
              </div>
            ) : (
              <>
                <button onClick={() => handlePin(s.session_id)}>
                  {s.pinned ? '📌 Unpin' : '📌 Pin to top'}
                </button>
                <button onClick={() => setDelConfirm(s.session_id)}>
                  🗑 Delete
                </button>
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-inner">
        {pinned.length > 0 && (
          <>
            <div className="sidebar-section-title">📌 Pinned</div>
            {pinned.map(renderItem)}
          </>
        )}

        {recent.length > 0 && (
          <>
            <div className="sidebar-section-title">Recent</div>
            {recent.map(renderItem)}
          </>
        )}

        {sessions.length === 0 && (
          <div className="sidebar-empty">
            No conversations yet. Ask your first question!
          </div>
        )}
      </div>
    </aside>
  );
}
