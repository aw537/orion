import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const BASE = import.meta.env.VITE_API_URL || '';

export function useInboxUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${BASE}/api/v1/inbox/upload`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `Upload failed: ${res.status}` }));
        throw new Error(err.detail || `Upload failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inbox-history'] });
    },
  });
}

export function useInboxHistory() {
  return useQuery({
    queryKey: ['inbox-history'],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/v1/inbox/history`);
      if (!res.ok) throw new Error(`Failed to fetch history: ${res.status}`);
      return res.json();
    },
  });
}
