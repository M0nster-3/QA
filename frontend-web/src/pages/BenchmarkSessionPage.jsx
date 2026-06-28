import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { benchmark, getToken } from '../api';
import BenchmarkSidebar from '../components/BenchmarkSidebar';

const FIELDS = [
  { key: 'problem',        label: 'Problem',               hint: 'The mathematical problem statement' },
  { key: 'origin',         label: 'Origin of the Problem',  hint: 'Source: paper title, competition, textbook, etc.' },
  { key: 'solution',       label: 'Solution to Problem',    hint: 'The correct solution (from reference model, e.g. GPT)' },
  { key: 'rubric',         label: 'Rubric',                 hint: 'Scoring criteria: keyword = N pts, partial = 10 pts, full = 100 pts' },
  { key: 'doubao_answer',  label: "Doubao Model's Answer",  hint: "Doubao model's full response to the problem" },
  { key: 'doubao_analysis', label: "Doubao Model's Answer Analysis", hint: 'Your analysis of why Doubao succeeded or failed' },
];

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

/* ── Progress steps shown during generation ── */
const PROGRESS_STEPS = [
  { after: 0,   text: 'Preparing input file…' },
  { after: 3,   text: 'Loading benchmark SKILL…' },
  { after: 8,   text: 'Reading input and template structure…' },
  { after: 15,  text: 'Processing problem & origin…' },
  { after: 30,  text: 'Translating solution (verbatim)…' },
  { after: 50,  text: 'Building rubric & comparison…' },
  { after: 80,  text: 'Writing review & appendix…' },
  { after: 120, text: 'Compiling final .tex document…' },
  { after: 180, text: 'Still working — large documents take time…' },
];

function useProgressText(generating) {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!generating) { setElapsed(0); return; }
    const start = Date.now();
    timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(timerRef.current);
  }, [generating]);

  let step = PROGRESS_STEPS[0];
  for (const s of PROGRESS_STEPS) {
    if (elapsed >= s.after) step = s;
  }
  return { text: step.text, elapsed };
}

export default function BenchmarkSessionPage() {
  const { sessionId } = useParams();
  const nav = useNavigate();

  const [form, setForm] = useState({ problem: '', origin: '', solution: '', rubric: '', doubao_answer: '', doubao_analysis: '' });
  const [pageTitle, setPageTitle] = useState('');
  const [sessions, setSessions] = useState([]);
  const [output, setOutput] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [error, setError] = useState('');
  const pollingRef = useRef(null);
  const autoSaveRef = useRef(null);
  const dirtyRef = useRef(false);        // 用户是否改过表单（区分初始加载和用户输入）

  const progress = useProgressText(generating);

  const loadSessions = useCallback(() => {
    benchmark.sessions().then(setSessions).catch(() => {});
    benchmark.detail(sessionId).then(data => { if (data?.title != null) setPageTitle(data.title); }).catch(() => {});
  }, [sessionId]);

  const loadDetail = useCallback(async () => {
    try {
      const data = await benchmark.detail(sessionId);
      setForm({
        problem: data.problem || '',
        origin: data.origin || '',
        solution: data.solution || '',
        rubric: data.rubric || '',
        doubao_answer: data.doubao_answer || '',
        doubao_analysis: data.doubao_analysis || '',
      });
      setOutput(data.output);
      setGenerating(data.generating);
      setPageTitle(data.title || '');
      dirtyRef.current = false;           // 从 DB 加载，不算脏
    } catch {}
  }, [sessionId]);

  useEffect(() => { loadSessions(); }, [loadSessions]);
  useEffect(() => { loadDetail(); }, [loadDetail]);

  // ── 离开页面 / 关闭标签时提醒未保存 ──
  useEffect(() => {
    const warn = (e) => {
      if (dirtyRef.current) { e.preventDefault(); e.returnValue = ''; }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);

  // ── 切换 session 时清理自动保存定时器 ──
  useEffect(() => {
    return () => { clearTimeout(autoSaveRef.current); };
  }, [sessionId]);

  // Poll while generating
  useEffect(() => {
    if (!generating) return;
    pollingRef.current = setInterval(async () => {
      try {
        const data = await benchmark.detail(sessionId);
        setOutput(data.output);
        setGenerating(data.generating);
        if (!data.generating) {
          clearInterval(pollingRef.current);
          loadSessions();
        }
      } catch {}
    }, 3000);
    return () => clearInterval(pollingRef.current);
  }, [generating, sessionId, loadSessions]);

  // ── 自动保存（防抖 2 秒，静默保存不弹提示）──
  const autoSave = useCallback(async (formData) => {
    if (generating) return;
    try {
      await benchmark.update(sessionId, formData);
      dirtyRef.current = false;
      setSaveMsg('Auto-saved ✓');
      setTimeout(() => setSaveMsg(prev => prev === 'Auto-saved ✓' ? '' : prev), 2000);
    } catch {}
  }, [sessionId, generating]);

  const updateField = (key, value) => {
    setForm(prev => {
      const next = { ...prev, [key]: value };
      // 标记脏 & 启动防抖自动保存
      dirtyRef.current = true;
      setSaveMsg('');
      clearTimeout(autoSaveRef.current);
      autoSaveRef.current = setTimeout(() => autoSave(next), 2000);
      return next;
    });
  };

  const allFilled = FIELDS.every(f => form[f.key].trim());
  const filledCount = FIELDS.filter(f => form[f.key].trim()).length;

  const save = async () => {
    clearTimeout(autoSaveRef.current);    // 取消待执行的自动保存
    setSaving(true); setError('');
    try {
      await benchmark.update(sessionId, form);
      dirtyRef.current = false;
      setSaveMsg('Saved ✓');
      loadSessions();
      setTimeout(() => setSaveMsg(''), 3000);
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  const generate = async () => {
    setError('');
    try {
      await save();
      await benchmark.generate(sessionId);
      setGenerating(true);
    } catch (e) { setError(e.message); }
  };

  const downloadTex = () => {
    fetch(`/api/benchmark/sessions/${sessionId}/download`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then(res => { if (!res.ok) throw new Error('Download failed'); return res.blob(); })
      .then(blob => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `benchmark_${sessionId}.tex`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(e => setError(e.message));
  };

  const copyTex = () => {
    if (output?.tex_content) {
      navigator.clipboard.writeText(output.tex_content)
        .then(() => setSaveMsg('Copied to clipboard ✓'))
        .catch(() => {});
      setTimeout(() => setSaveMsg(''), 2000);
    }
  };

  const createNew = async () => {
    try { const { session_id } = await benchmark.create({}); nav(`/benchmark/${session_id}`); } catch {}
  };

  const isDone = output?.status === 'done' && output?.tex_content;
  const isError = output?.status === 'error';

  return (
    <div className="app-layout">
      <BenchmarkSidebar
        sessions={sessions}
        activeId={sessionId}
        onSelect={(id) => nav(`/benchmark/${id}`)}
        onRefresh={loadSessions}
        onNew={createNew}
      />

      <main className="main-content">
        <div className="bench-container">
          <h2 className="bench-title">{pageTitle || 'Untitled'}</h2>

          <div className="bench-form">
            {FIELDS.map(f => (
              <div key={f.key} className="bench-field">
                <label className="bench-label">
                  {f.label}
                  {form[f.key].trim() ? <span className="field-ok"> ✓</span> : <span className="field-req"> *</span>}
                </label>
                <p className="bench-hint">{f.hint}</p>
                <textarea
                  value={form[f.key]}
                  onChange={e => updateField(f.key, e.target.value)}
                  rows={f.key === 'solution' || f.key === 'doubao_answer' ? 10 : 4}
                  disabled={generating}
                  placeholder={f.hint}
                />
              </div>
            ))}
          </div>

          {error && <div className="home-error">{error}</div>}

          <div className="bench-actions">
            <button onClick={save} disabled={saving || generating} className="btn-save">
              {saving ? 'Saving…' : 'Save Draft'}
            </button>
            {saveMsg && <span className="save-msg">{saveMsg}</span>}
            <div className="bench-actions-right">
              {isDone && (
                <button onClick={generate} disabled={generating || !allFilled} className="btn-regen">↻ Regenerate</button>
              )}
              {!isDone && (
                <button onClick={generate} disabled={generating || !allFilled} className="btn-generate">
                  {generating ? '⏳ Generating…' : 'Generate .tex'}
                </button>
              )}
            </div>
          </div>

          {!allFilled && !generating && (
            <p className="bench-incomplete">
              Fill all 6 fields to enable generation. ({filledCount}/6 filled, {6 - filledCount} remaining)
            </p>
          )}

          {generating && (
            <div className="bench-status">
              <div className="bench-status-header">
                <span className="spinner">⏳</span>
                <span>DeepSeek V4 Pro is generating your benchmark document…</span>
              </div>
              <div className="bench-progress">
                <span className="bench-progress-step">{progress.text}</span>
                <span className="bench-progress-time">{Math.floor(progress.elapsed / 60)}:{String(progress.elapsed % 60).padStart(2, '0')}</span>
              </div>
              <p className="bench-pipeline-note">
                Pipeline: input.md → SKILL processing → output.tex
              </p>
            </div>
          )}

          {isDone && (
            <div className="bench-result">
              <div className="bench-result-header">
                <span>✅ Generated: {formatTime(output.generated_at)}</span>
                <div className="bench-result-actions">
                  <button onClick={copyTex} className="btn-copy-tex">📋 Copy</button>
                  <button onClick={downloadTex} className="btn-download">📥 Download .tex</button>
                </div>
              </div>
              <details className="bench-preview">
                <summary>Preview LaTeX source ({output.tex_content.split('\n').length} lines)</summary>
                <pre className="bench-tex-pre">{output.tex_content}</pre>
              </details>
            </div>
          )}

          {isError && (
            <div className="bench-error-result">
              ❌ Generation failed: {output.tex_content}
              <button onClick={generate} disabled={generating || !allFilled} className="btn-regen" style={{ marginLeft: 12 }}>↻ Retry</button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
