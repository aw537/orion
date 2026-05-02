import { create } from 'zustand';

interface NebulaEvent { event_id: number; action_type: string; planet_id?: string; biome_id?: string; record_id?: string; initiated_by: string; timestamp: string; payload_before?: string; payload_after?: string; confidence_delta?: number; }

interface NebulaState {
  events: NebulaEvent[];
  addEvent: (e: NebulaEvent) => void;
}

export const useNebulaStore = create<NebulaState>((set) => ({
  events: [],
  addEvent: (e) => set((s) => ({ events: [e, ...s.events].slice(0, 50) })),
}));
