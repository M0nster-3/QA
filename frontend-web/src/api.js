const BASE = '/api';
let token = localStorage.getItem('token') || '';

export function setToken(t) { token = t; if (t) localStorage.setItem('token', t); else localStorage.removeItem('token'); }
export function getToken() { return token; }
export function setStoredUsername(u) { if (u) localStorage.setItem('username', u); else localStorage.removeItem('username'); }
export function getStoredUsername() { return localStorage.getItem('username') || ''; }

let _refreshing = null;
async function silentReLogin() {
  const username = getStoredUsername();
  if (!username) return false;
  if (_refreshing) return _refreshing;
  _refreshing = (async () => {
    try {
      const res = await fetch(BASE + '/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username }) });
      if (!res.ok) return false;
      const data = await res.json();
      setToken(data.access_token);
      return true;
    } catch { return false; }
    finally { _refreshing = null; }
  })();
  return _refreshing;
}

async function request(path, options = {}, _retried = false) {
  const headers = { ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch(BASE + path, {
    ...options, headers,
    body: options.body instanceof FormData ? options.body : (options.body && typeof options.body === 'object' ? JSON.stringify(options.body) : options.body),
  });
  if (res.status === 401 && !_retried) { const ok = await silentReLogin(); if (ok) return request(path, options, true); setToken(''); window.location.href = '/login'; throw new Error('Unauthorized'); }
  if (!res.ok) { const text = await res.text(); let msg = text; try { const j = JSON.parse(text); msg = j.detail || text; } catch {} throw new Error(msg); }
  return res;
}

export const auth = {
  login: (username) => request('/auth/login', { method: 'POST', body: { username } }).then(r => r.json()),
  me: () => request('/auth/me').then(r => r.json()),
};

export const ai = {
  sessions: () => request('/ai/sessions').then(r => r.json()),
  sessionDetail: (id) => request(`/ai/sessions/${id}`).then(r => r.json()),
  hideSession: (id) => request(`/ai/sessions/${id}/hide`, { method: 'POST' }).then(r => r.json()),
  pinSession: (id) => request(`/ai/sessions/${id}/pin`, { method: 'POST' }).then(r => r.json()),
};

export const benchmark = {
  create: (fields) => request('/benchmark/sessions', { method: 'POST', body: fields }).then(r => r.json()),
  update: (id, fields) => request(`/benchmark/sessions/${id}`, { method: 'PUT', body: fields }).then(r => r.json()),
  sessions: () => request('/benchmark/sessions').then(r => r.json()),
  detail: (id) => request(`/benchmark/sessions/${id}`).then(r => r.json()),
  generate: (id) => request(`/benchmark/sessions/${id}/generate`, { method: 'POST' }).then(r => r.json()),
  rename: (id, title) => request(`/benchmark/sessions/${id}/rename`, { method: 'POST', body: { title } }).then(r => r.json()),
  pin: (id) => request(`/benchmark/sessions/${id}/pin`, { method: 'POST' }).then(r => r.json()),
  hide: (id) => request(`/benchmark/sessions/${id}/hide`, { method: 'POST' }).then(r => r.json()),
};
