import { createContext, useContext, useState, useEffect } from 'react';
import { setToken, getToken, setStoredUsername, getStoredUsername, auth } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // ── 启动时恢复会话 ────────────────────────────────────────
  useEffect(() => {
    (async () => {
      // 1) 已有 token → 验证
      if (getToken()) {
        try {
          const u = await auth.me();
          setUser(u);
          setLoading(false);
          return;
        } catch {
          // token 失效，走下面的自动重登录
          setToken('');
        }
      }

      // 2) 没有有效 token，但有保存的 username → 静默登录
      const saved = getStoredUsername();
      if (saved) {
        try {
          const res = await auth.login(saved);
          setToken(res.access_token);
          setUser({ user_id: res.user_id, username: res.username });
          setLoading(false);
          return;
        } catch {
          // 静默登录也失败 → 清空，让用户手动输入
          setStoredUsername('');
          setToken('');
        }
      }

      setLoading(false);
    })();
  }, []);

  // ── 手动登录 ──────────────────────────────────────────────
  const login = async (username) => {
    const res = await auth.login(username);
    setToken(res.access_token);
    setStoredUsername(username);          // 持久化用户名
    setUser({ user_id: res.user_id, username: res.username });
    return res;
  };

  // ── 切换用户（彻底注销）──────────────────────────────────
  const logout = () => {
    setToken('');
    setStoredUsername('');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() { return useContext(AuthContext); }
