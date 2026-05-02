import { apiClient } from './client';
import { useQuery } from '@tanstack/react-query';

export interface GraphEntity {
  id: string;
  name: string;
  type: string;
  tier: number;
  mentions: number;
  degree: number;
  planet_id: string | null;
  planet_name: string | null;
  planet_color: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  confidence: number;
  strength: number;
}

export interface PlanetInfo {
  id: string;
  name: string;
  color: string;
}

export interface FullGraph {
  entities: GraphEntity[];
  edges: GraphEdge[];
  planets: PlanetInfo[];
}

export interface GraphNeighborhood {
  center_entity_id: string;
  entities: GraphEntity[];
  edges: GraphEdge[];
  depth: number;
}

export interface HubEntity {
  id: string;
  name: string;
  entity_type: string;
  tier: number;
  degree: number;
}

export interface UnlinkedMention {
  entity_id: string;
  entity_name: string;
  unlinked_count: number;
  stardust_ids: string[];
  sample: string;
}

export const useFullGraph = () =>
  useQuery({ queryKey: ['graph-full'], queryFn: () => apiClient.get<FullGraph>('/api/v1/graph/full') });

export const useEntityNeighborhood = (entityId: string | null, depth = 2) =>
  useQuery({
    queryKey: ['graph-neighborhood', entityId, depth],
    queryFn: () => apiClient.get<GraphNeighborhood>(`/api/v1/graph/entity/${entityId}/neighborhood?depth=${depth}`),
    enabled: !!entityId,
  });

export const useGraphHubs = (limit = 10) =>
  useQuery({ queryKey: ['graph-hubs', limit], queryFn: () => apiClient.get<HubEntity[]>(`/api/v1/graph/hubs?limit=${limit}`) });

export const useUnlinkedMentions = () =>
  useQuery({ queryKey: ['unlinked-mentions'], queryFn: () => apiClient.get<UnlinkedMention[]>('/api/v1/graph/unlinked-mentions') });

export const linkAll = (entityId: string) => apiClient.post(`/api/v1/graph/link-all/${entityId}`);
