const BASE = import.meta.env.VITE_API_URL || '';

export const apiClient = {
  async get<T = any>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`);
    if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
    return res.json();
  },
  async post<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
    if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
    return res.json();
  },
  async put<T = any>(path: string, body?: any): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
    if (!res.ok) throw new Error(`PUT ${path}: ${res.status}`);
    return res.json();
  },
  async delete<T = any>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`DELETE ${path}: ${res.status}`);
    return res.json();
  },
  sseUrl(path: string): string { return `${BASE}${path}`; },
};
