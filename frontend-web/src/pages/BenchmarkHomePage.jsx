import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { benchmark } from '../api';
import BenchmarkSidebar from '../components/BenchmarkSidebar';

export default function BenchmarkHomePage() {
  const nav = useNavigate();
  const [sessions, setSessions] = useState([]);

  const load = useCallback(() => {
    benchmark.sessions().then(setSessions).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const createNew = async () => {
    try {
      const { session_id } = await benchmark.create({});
      nav(`/benchmark/${session_id}`);
    } catch {}
  };

  return (
    <div className="app-layout">
      <BenchmarkSidebar
        sessions={sessions}
        activeId={null}
        onSelect={(id) => nav(`/benchmark/${id}`)}
        onRefresh={load}
        onNew={createNew}
      />
      <main className="main-content">
        <div className="home-center">
          <h1 className="home-title">Benchmark Make</h1>
          <p className="home-subtitle">Generate structured LaTeX benchmark documents</p>
          <button className="bench-create-btn" onClick={createNew}>
            + Create New Benchmark
          </button>
        </div>
      </main>
    </div>
  );
}
