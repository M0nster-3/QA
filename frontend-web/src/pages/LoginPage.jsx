import { useState } from 'react';
import { useAuth } from '../AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!username.trim()) return;
    setError('');
    setLoading(true);
    try {
      await login(username.trim());
    } catch (err) {
      setError(err.message || 'Login failed');
    }
    setLoading(false);
  };

  return (
    <div className="login-page">
      <form onSubmit={submit} className="login-form">
        <h1>QA</h1>
        <p className="subtitle">Mathematical Paper Platform</p>
        <p className="subtitle hint">
          Enter a username to continue — your history is kept automatically
        </p>
        {error && <div className="error">{error}</div>}
        <input
          value={username}
          onChange={e => setUsername(e.target.value)}
          placeholder="Username"
          required
          autoFocus
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Enter'}
        </button>
      </form>
    </div>
  );
}
