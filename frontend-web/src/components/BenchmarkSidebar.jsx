import { useState, useEffect, useRef } from 'react';
import { benchmark } from '../api';

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  const dateOnly = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  if (dateOnly.getTime() === today.getTime()) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  if (dateOnly.getTime() === yesterday.getTime()) return 'Yesterday';
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
}

export default function BenchmarkSidebar({ sessions, activeId, onSelect, onRefresh, onNew }) {
  const [menuOpen, setMenuOpen] = useState(null);
  const [renaming, setRenaming] = useState(null);
  const [renameVal, setRenameVal] = useState('');
  const [delConfirm, setDelConfirm] = useState(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (menuOpen === null) return;
    const close = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(null); setDelConfirm(null); setRenaming(null);
      }
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [menuOpen]);

  const handlePin = async (id) => {
    setMenuOpen(null);
    try { await benchmark.pin(id); onRefresh(); } catch {}
  };

  const handleDelete = async (id) => {
    try { await benchmark.hide(id); onRefresh(); } catch {}
    setMenuOpen(null); setDelConfirm(null);
  };

  const startRename = (s) => {
    setRenaming(s.session_id);
    setRenameVal(s.title);
    setDelConfirm(null);
  };

  const submitRename = async (id) => {
    const t = renameVal.trim();
    if (t) {
      try { await benchmark.rename(id, t); onRefresh(); } catch {}
    }
    setRenaming(null); setMenuOpen(null);
  };

  const pinned = sessions.filter(s => s.pinned);
  const recent = sessions.filter(s => !s.pinned);

  const renderItem = (s) => {
    const isActive = String(s.session_id) === String(activeId);
    const isMenuTarget = menuOpen === s.session_id;
    const isRenaming = renaming === s.session_id;

    return (
      <div
        key={s.session_id}
        className={`session-item${isActive ? ' active' : ''}${s.pinned ? ' pinned' : ''}`}
        onClick={() => { if (!isRenaming) onSelect(s.session_id); }}
      >
        <div className="session-item-row">
          {isRenaming ? (
            <input
              value={renameVal}
              onChange={e => setRenameVal(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') submitRename(s.session_id);
                if (e.key === 'Escape') { setRenaming(null); }
              }}
              onBlur={() => submitRename(s.session_id)}
              autoFocus
              className="rename-inline"
              onClick={e => e.stopPropagation()}
            />
          ) : (
            <>
              <span className="session-item-q">
                {s.generating && <span className="item-running">⏳ </span>}
                {s.title}
              </span>
              <button
                className="session-item-menu"
                onClick={e => { e.stopPropagation(); setMenuOpen(isMenuTarget ? null : s.session_id); setDelConfirm(null); }}
              >⋯</button>
            </>
          )}
        </div>
        {!isRenaming && <div className="session-item-meta">{formatTime(s.updated_at)}</div>}

        {isMenuTarget && !isRenaming && (
          <div className="session-item-dropdown" ref={menuRef} onClick={e => e.stopPropagation()}>
            {delConfirm === s.session_id ? (
              <div className="del-confirm">
                <span>Delete?</span>
                <button className="del-yes" onClick={() => handleDelete(s.session_id)}>Yes</button>
                <button className="del-no" onClick={() => { setDelConfirm(null); setMenuOpen(null); }}>No</button>
              </div>
            ) : (
              <>
                <button onClick={() => { startRename(s); setMenuOpen(null); }}>✏️ Rename</button>
                <button onClick={() => handlePin(s.session_id)}>
                  {s.pinned ? '📌 Unpin' : '📌 Pin to top'}
                </button>
                <button onClick={() => setDelConfirm(s.session_id)}>🗑 Delete</button>
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
        <button className="bench-new-btn" onClick={onNew}>+ New Benchmark</button>

        {pinned.length > 0 && <div className="sidebar-section-title">📌 Pinned</div>}
        {pinned.map(renderItem)}

        {recent.length > 0 && <div className="sidebar-section-title">Recent</div>}
        {recent.map(renderItem)}

        {sessions.length === 0 && (
          <div className="sidebar-empty">No benchmarks yet. Create your first one!</div>
        )}
      </div>
    </aside>
  );
}
