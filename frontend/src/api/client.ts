const BASE = import.meta.env.VITE_API_URL || '';

function _authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = localStorage.getItem('orion_token') ?? sessionStorage.getItem('orion_token');
  const headers: Record<string, string> = { ...extra };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export const apiClient = {
  async get<T = any>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { headers: _authHeaders() });
    if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
    return res.json();
  },
  async post<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: _authHeaders({ 'Content-Type': 'application/json' }),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      let detail: string | undefined;
      try { detail = (await res.json()).detail; } catch { /* ignore */ }
      const err = new Error(detail ?? `POST ${path}: ${res.status}`) as Error & { status: number };
      err.status = res.status;
      throw err;
    }
    return res.json();
  },
  async put<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
      method: 'PUT',
      headers: _authHeaders({ 'Content-Type': 'application/json' }),
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`PUT ${path}: ${res.status}`);
    return res.json();
  },
  async delete<T = any>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { method: 'DELETE', headers: _authHeaders() });
    if (!res.ok) throw new Error(`DELETE ${path}: ${res.status}`);
    return res.json();
  },
  sseUrl(path: string): string { return `${BASE}${path}`; },
};
