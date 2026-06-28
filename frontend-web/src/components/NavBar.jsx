import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function NavBar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();

  const isQa = loc.pathname === '/' || loc.pathname.startsWith('/session');
  const isBench = loc.pathname.startsWith('/benchmark');

  return (
    <nav className="navbar">
      <div className="nav-left">
        <Link to="/" className="nav-brand">QA</Link>
        <button
          className={`btn-nav${isQa ? ' active' : ''}`}
          onClick={() => nav('/')}
        >
          AI Q&A
        </button>
        <button
          className={`btn-nav${isBench ? ' active' : ''}`}
          onClick={() => nav('/benchmark')}
        >
          Benchmark
        </button>
      </div>
      <div className="nav-right">
        <span className="nav-user">{user?.username}</span>
        <button
          onClick={() => { logout(); nav('/login'); }}
          className="btn-sm"
          title="Switch user"
        >
          Switch User
        </button>
      </div>
    </nav>
  );
}
