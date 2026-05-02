import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';

export const usePlanets = () => useQuery({ queryKey: ['planets'], queryFn: () => apiClient.get('/api/v1/planets') });
export const usePlanet = (id: string) => useQuery({ queryKey: ['planet', id], queryFn: () => apiClient.get(`/api/v1/planets/${id}`), enabled: !!id });
