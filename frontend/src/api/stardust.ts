import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';

export const useStardust = (id: string) => useQuery({ queryKey: ['stardust', id], queryFn: () => apiClient.get(`/api/v1/stardust/${id}`), enabled: !!id });
export const useEntity = (id: string) => useQuery({ queryKey: ['entity', id], queryFn: () => apiClient.get(`/api/v1/entities/${id}`), enabled: !!id });
