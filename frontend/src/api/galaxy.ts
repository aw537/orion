import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';

export const useGalaxy = () => useQuery({ queryKey: ['galaxy'], queryFn: () => apiClient.get('/api/v1/galaxy') });
export const useGalaxyStrength = () => useQuery({ queryKey: ['galaxy', 'strength'], queryFn: () => apiClient.get('/api/v1/galaxy/strength') });
export const useGalaxyStatus = () => useQuery({ queryKey: ['galaxy', 'status'], queryFn: () => apiClient.get('/api/v1/galaxy/status') });
