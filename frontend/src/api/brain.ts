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

export const askBrain = (question: string, planet?: string) =>
  apiClient.post<AskResult>('/api/v1/ask', { question, planet });
