import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { Panel } from '../ui';

interface Contradiction {
  id: string; record_a_id: string; record_b_id: string;
  conflict_type: string; status: string; region: string; detected_at: string | null;
}

const RESOLUTION_TYPES = [
  { value: 'a_supersedes_b', label: 'A wins', desc: 'Keep A, deprecate B' },
  { value: 'b_supersedes_a', label: 'B wins', desc: 'Keep B, deprecate A' },
  { value: 'coexist', label: 'Both valid', desc: 'Different contexts' },
  { value: 'synthesize', label: 'Merge', desc: 'Create new combined record' },
];

interface Props { open: boolean; onClose: () => void }

export default function ContradictionPanel({ open, onClose }: Props) {
  const qc = useQueryClient();
  const trapRef = useFocusTrap<HTMLDivElement>(open);
  const [resolving, setResolving] = useState<string | null>(null);
  const [resType, setResType] = useState('a_supersedes_b');
  const [synthContent, setSynthContent] = useState('');
  const [resolved, setResolved] = useState<Set<string>>(new Set());

  const { data } = useQuery({
    queryKey: ['contradictions'],
    queryFn: () => apiClient.get<{ contradictions: Contradiction[] }>('/api/v1/contradictions'),
    enabled: open,
  });

  const resolve = useMutation({
    mutationFn: (args: { id: string; resolution_type: string; synthesis_content?: string }) =>
      apiClient.post(`/api/v1/contradictions/${args.id}/resolve`, {
        resolution_type: args.resolution_type,
        synthesis_content: args.synthesis_content || null,
      }),
    onSuccess: (_, vars) => {
      setResolved((s) => new Set(s).add(vars.id));
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['contradictions'] });
        qc.invalidateQueries({ queryKey: ['galaxy'] });
        setResolving(null);
        setSynthContent('');
      }, 600);
    },
  });

  const items = (data?.contradictions ?? []).filter((c) => !resolved.has(c.id));

  if (!open) return null;

  return (
    <Panel ref={trapRef} width="md">
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-soft)]">
        <h2 className="font-display text-base font-medium">Contradictions</h2>
        <button onClick={onClose} className="w-8 h-8 rounded-full bg-transparent border border-[var(--border-soft)] text-[var(--text-2)] flex items-center justify-center hover:text-[var(--text-1)]" aria-label="Close">&times;</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {items.length === 0 && <p className="text-xs text-[var(--text-3)] text-center py-8">No unresolved contradictions</p>}
        {items.map((c) => (
          <div
            key={c.id}
            className="p-3.5 bg-[var(--surface-3)] border border-[var(--border-soft)] rounded-lg transition-all duration-500"
            style={{ opacity: resolved.has(c.id) ? 0 : 1, transform: resolved.has(c.id) ? 'translateX(100%)' : 'none' }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[#F59E0B]">{c.conflict_type}</span>
              <span className="text-[10px] text-[var(--text-3)] font-mono">{c.region}</span>
            </div>
            <div className="text-[11px] text-[var(--text-2)] space-y-1 mb-3">
              <div className="truncate">A: <span className="text-[var(--text-1)]">{c.record_a_id.slice(0, 8)}…</span></div>
              <div className="truncate">B: <span className="text-[var(--text-1)]">{c.record_b_id.slice(0, 8)}…</span></div>
            </div>
            {resolving === c.id ? (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-1.5">
                  {RESOLUTION_TYPES.map((r) => (
                    <button
                      key={r.value}
                      onClick={() => setResType(r.value)}
                      className={`px-2 py-1.5 rounded text-[10px] border transition-all ${resType === r.value ? 'border-[var(--violet-300)] bg-[rgba(124,58,237,0.2)] text-[var(--text-1)]' : 'border-[var(--border-soft)] text-[var(--text-3)] hover:text-[var(--text-2)]'}`}
                    >{r.label}</button>
                  ))}
                </div>
                {resType === 'synthesize' && (
                  <textarea
                    value={synthContent}
                    onChange={(e) => setSynthContent(e.target.value)}
                    placeholder="Combined understanding..."
                    className="w-full h-16 px-2.5 py-2 bg-[var(--surface-2)] border border-[var(--border-soft)] rounded text-xs text-[var(--text-1)] placeholder:text-[var(--text-3)] outline-none resize-none"
                  />
                )}
                <div className="flex gap-2">
                  <button onClick={() => setResolving(null)} className="flex-1 px-2 py-1.5 rounded text-[10px] border border-[var(--border-soft)] text-[var(--text-3)]">Cancel</button>
                  <button
                    onClick={() => resolve.mutate({ id: c.id, resolution_type: resType, synthesis_content: resType === 'synthesize' ? synthContent : undefined })}
                    disabled={resolve.isPending}
                    className="flex-1 px-2 py-1.5 rounded text-[10px] bg-[var(--violet-300)] text-[var(--surface-1)] font-medium disabled:opacity-50"
                  >{resolve.isPending ? 'Resolving...' : 'Resolve'}</button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setResolving(c.id)}
                className="w-full px-2 py-1.5 rounded text-[10px] border border-[var(--border-soft)] text-[var(--text-2)] hover:text-[var(--text-1)] hover:border-[var(--border)] transition-all"
              >Resolve →</button>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}
