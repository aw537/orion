import { apiClient } from './client';

export interface AskResult {
  question: string;
  intent: string;
  answer: string;
  supporting_records?: any[];
  graph_path?: any;
  graph_neighborhood?: any;
  key_decisions?: string[];
  open_questions?: string[];
  confidence?: number;
}

export interface MergeProposal {
  id: string;
  source_galaxy_id: string;
  target_galaxy_id: string;
  status: string;
  proposed_by: string;
  accepted_by: string | null;
  entity_mappings_count: number;
  bridges_created: number;
  created_at: string | null;
  completed_at: string | null;
  rejection_reason: string | null;
}

export const askBrain = (question: string, planet?: string) =>
  apiClient.post<AskResult>('/api/v1/ask', { question, planet });

export const proposeMerge = (targetGalaxyId: string) =>
  apiClient.post<{ proposal_id: string; status: string }>('/api/v1/galaxy/merge/propose', { target_galaxy_id: targetGalaxyId });

export const acceptMerge = (proposalId: string) =>
  apiClient.post<{ proposal_id: string; status: string }>(`/api/v1/galaxy/merge/${proposalId}/accept`);

export const rejectMerge = (proposalId: string, reason: string) =>
  apiClient.post<{ proposal_id: string; status: string }>(`/api/v1/galaxy/merge/${proposalId}/reject`, { reason });

export const getMergeProposal = (proposalId: string) =>
  apiClient.get<MergeProposal>(`/api/v1/galaxy/merge/${proposalId}`);

export const getMergeSunPreview = (proposalId: string) =>
  apiClient.get<Record<string, any>>(`/api/v1/galaxy/merge/${proposalId}/sun-preview`);

export const getMergeEntityMappings = (proposalId: string) =>
  apiClient.get<any[]>(`/api/v1/galaxy/merge/${proposalId}/entity-mappings`);

export const executeMerge = (proposalId: string) =>
  apiClient.post<{ status: string; entities_merged: number; bridges_created: number }>(`/api/v1/galaxy/merge/${proposalId}/execute`);
