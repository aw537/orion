import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';

export const useBiome = (id: string) => useQuery({ queryKey: ['biome', id], queryFn: () => apiClient.get(`/api/v1/biomes/${id}`), enabled: !!id });
export const useBiomeGraph = (id: string) => useQuery({ queryKey: ['biome', id, 'graph'], queryFn: () => apiClient.get(`/api/v1/biomes/${id}/graph`), enabled: !!id });
export const useBiomeStardust = (id: string, limit = 100) => useQuery({ queryKey: ['biome', id, 'stardust'], queryFn: () => apiClient.get(`/api/v1/biomes/${id}/stardust?limit=${limit}`), enabled: !!id });
