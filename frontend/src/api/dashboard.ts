import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';

export const useModelProfiles = () => useQuery({ queryKey: ['model-profiles'], queryFn: () => apiClient.get('/api/v1/model-profiles') });
export const useNebulaDashboard = (days = 30) => useQuery({ queryKey: ['nebula', 'dashboard', days], queryFn: () => apiClient.get(`/api/v1/nebula/dashboard?days=${days}`), refetchInterval: 60_000 });
export const useCacheTTLConfig = () => useQuery({ queryKey: ['cache', 'ttl-config'], queryFn: () => apiClient.get('/api/v1/cache/ttl-config') });
export const useSessionsDaily = (days = 30) => useQuery({ queryKey: ['admin', 'sessions-daily', days], queryFn: () => apiClient.get(`/api/v1/admin/sessions/daily?days=${days}`) });
export const useAdminActiveAgents = () => useQuery({ queryKey: ['admin', 'agents-active'], queryFn: () => apiClient.get('/api/v1/admin/agents/active'), refetchInterval: 30_000 });
export const useNebula = (limit = 20) => useQuery({ queryKey: ['nebula', 'events', limit], queryFn: () => apiClient.get(`/api/v1/nebula?limit=${limit}`), refetchInterval: 15_000 });
