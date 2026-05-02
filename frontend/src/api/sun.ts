import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';

export const useSun = () => useQuery({ queryKey: ['sun'], queryFn: () => apiClient.get('/api/v1/sun') });
export const useEvolutionLog = () => useQuery({ queryKey: ['sun', 'evolution-log'], queryFn: () => apiClient.get('/api/v1/sun/evolution-log') });

export function useUpdateSunSection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, content, summary }: { key: string; content: any; summary?: string }) =>
      apiClient.put(`/api/v1/sun/${key}`, { content, changed_by: 'user', summary: summary || '' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sun'] }); },
  });
}

export function useAddBlocker() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (blocker: string) => apiClient.post('/api/v1/sun/working-context/add-blocker', { blocker }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sun'] }); },
  });
}

export function useAddDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ decision, biome }: { decision: string; biome?: string }) =>
      apiClient.post('/api/v1/sun/working-context/add-decision', { decision, biome: biome || '' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sun'] }); },
  });
}

export function useReimportSteeringDoc() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post('/api/v1/sun/steering-doc/reimport'),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sun'] }); },
  });
}
