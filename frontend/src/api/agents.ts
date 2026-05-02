import { apiClient } from './client';
import { useQuery } from '@tanstack/react-query';

export interface AgentIdentity {
  id: string;
  agent_name: string;
  agent_type: string;
  current_model: string;
  model_family: string;
  total_sessions: number;
  total_reads: number;
  total_writes: number;
  retrieval_quality_score: number;
  calibration_score?: number;
  last_active: string | null;
  birth_date: string | null;
}

export interface AgentExpertise {
  domain: string;
  level: number;
  evidence_count: number;
  last_demonstrated: string | null;
}

export interface BrainHealth {
  overall_health: number;
  knowledge_freshness: number;
  total_knowledge_items: number;
  coverage_gaps: string[];
  stale_beliefs: { id: string; content: string }[];
  expertise_summary: AgentExpertise[];
  recommended_enrichment: string[];
  agent_sessions: number;
  current_model: string;
  brain_age_days: number;
}

export interface ModelSwitch {
  agent_name?: string;
  previous_model: string;
  new_model: string;
  switched_at: string;
  continuity_score: number;
}

export const useAgents = () => useQuery({ queryKey: ['agents'], queryFn: () => apiClient.get<AgentIdentity[]>('/api/v1/agents') });
export const useAgent = (name: string) => useQuery({ queryKey: ['agent', name], queryFn: () => apiClient.get<AgentIdentity>(`/api/v1/agents/${name}`), enabled: !!name });
export const useAgentExpertise = (name: string) => useQuery({ queryKey: ['agent-expertise', name], queryFn: () => apiClient.get<AgentExpertise[]>(`/api/v1/agents/${name}/expertise`), enabled: !!name });
export const useAgentHealth = (name: string) => useQuery({ queryKey: ['agent-health', name], queryFn: () => apiClient.get<BrainHealth>(`/api/v1/agents/${name}/health`), enabled: !!name });
