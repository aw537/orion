import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '../../api/client';
import { ConfirmDialog } from '../ui';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface SynthesisResult {
  topic: string; current_understanding: string; key_decisions: string[];
  open_questions: string[]; contradictions: string[]; confidence: number;
  record_count: number; last_updated: string | null;
}

interface Props { open: boolean; onClose: () => void; initialTopic?: string }

export default function SynthesisPanel({ open, onClose, initialTopic }: Props) {
  const [topic, setTopic] = useState(initialTopic || '');
  const [result, setResult] = useState<SynthesisResult | null>(null);
  const [confirmRefresh, setConfirmRefresh] = useState(false);
  const trapRef = useFocusTrap<HTMLDivElement>(open);

  const synthesize = useMutation({
    mutationFn: (t: string) => apiClient.post<SynthesisResult>('/api/v1/synthesize', { topic: t }),
    onSuccess: (data) => setResult(data),
  });

  const refresh = useMutation({
    mutationFn: async (t: string) => {
      await apiClient.delete('/api/v1/synthesize/cache');
      return apiClient.post<SynthesisResult>('/api/v1/synthesize', { topic: t });
    },
    onSuccess: (data) => setResult(data),
  });

  if (!open) return null;

  return (
    <div className="absolute inset-0 z-[20] flex items-center justify-center" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="absolute inset-0 bg-[rgba(7,4,26,0.85)] backdrop-blur-sm" onClick={onClose} />
      <div ref={trapRef} className="relative w-[680px] max-w-[90vw] max-h-[80vh] bg-[rgba(7,4,26,0.96)] border border-[var(--border)] rounded-[14px] shadow-[0_40px_80px_rgba(0,0,0,0.6)] overflow-hidden flex flex-col" role="dialog" aria-modal="true" aria-label="Synthesize knowledge">
        {/* Header */}
        <div className="flex items-center gap-3.5 px-5 py-4 border-b border-[var(--border-soft)]">
          <span className="text-lg"></span>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && topic.trim()) synthesize.mutate(topic.trim()); }}
            placeholder="What do you want to synthesize?"
            className="flex-1 bg-transparent border-0 outline-none text-[var(--text-1)] text-[17px] placeholder:text-[var(--text-3)]"
            autoFocus
          />
          <button
            onClick={() => topic.trim() && synthesize.mutate(topic.trim())}
            disabled={synthesize.isPending || !topic.trim()}
            className="px-3.5 py-1.5 rounded-full bg-[var(--violet-300)] text-[var(--surface-1)] text-xs font-medium disabled:opacity-40"
          >{synthesize.isPending ? 'Thinking…' : 'Synthesize'}</button>
        </div>

        {/* Result */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {!result && !synthesize.isPending && (
            <p className="text-sm text-[var(--text-3)] text-center py-12">Enter a topic and press Synthesize to generate a knowledge synthesis.</p>
          )}
          {result && (
            <>
              {/* Meta */}
              <div className="flex items-center gap-3 text-[11px] text-[var(--text-3)]">
                <span className="font-mono">{result.record_count} records</span>
                <span>·</span>
                <span>confidence {(result.confidence * 100).toFixed(0)}%</span>
                {result.last_updated && <><span>·</span><span>updated {new Date(result.last_updated).toLocaleDateString()}</span></>}
                <button
                  onClick={() => setConfirmRefresh(true)}
                  disabled={refresh.isPending}
                  className="ml-auto inline-flex items-center gap-1 px-2 py-1 rounded border border-[var(--border-soft)] text-[var(--text-2)] hover:text-[var(--text-1)] hover:border-[var(--border)] transition-all"
                  title="Invalidate cache and regenerate"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={refresh.isPending ? 'animate-spin' : ''}><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
                  {refresh.isPending ? 'Refreshing…' : 'Refresh'}
                </button>
              </div>

              {/* Current Understanding */}
              <section>
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-2">Current Understanding</h3>
                <p className="text-sm text-[var(--text-1)] leading-relaxed whitespace-pre-wrap">{result.current_understanding}</p>
              </section>

              {/* Key Decisions */}
              {result.key_decisions.length > 0 && (
                <section>
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-2">Key Decisions</h3>
                  <ul className="space-y-1.5">
                    {result.key_decisions.map((d, i) => (
                      <li key={i} className="text-sm text-[var(--text-1)] flex gap-2"><span className="text-[var(--violet-300)]">•</span>{d}</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Open Questions */}
              {result.open_questions.length > 0 && (
                <section>
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#F59E0B] mb-2">Open Questions</h3>
                  <ul className="space-y-1.5">
                    {result.open_questions.map((q, i) => (
                      <li key={i} className="text-sm text-[var(--text-2)] flex gap-2"><span className="text-[#F59E0B]">?</span>{q}</li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Contradictions */}
              {result.contradictions.length > 0 && (
                <section>
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#F87171] mb-2">Contradictions</h3>
                  <ul className="space-y-1.5">
                    {result.contradictions.map((c, i) => (
                      <li key={i} className="text-sm text-[var(--text-2)] flex gap-2"><span className="text-[#F87171]">&bull;</span>{c}</li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--border-soft)] bg-[rgba(45,27,105,0.2)] text-[11px] text-[var(--text-3)]">
          <span>Synthesis is generated from your Galaxy's knowledge</span>
          <button onClick={onClose} className="text-[var(--text-2)] hover:text-[var(--text-1)]">Close</button>
        </div>
      </div>
      <ConfirmDialog
        open={confirmRefresh}
        title="Clear synthesis cache?"
        message="This will invalidate the cached synthesis and regenerate it from scratch. This cannot be undone."
        confirmLabel="Clear & Refresh"
        onConfirm={() => { setConfirmRefresh(false); refresh.mutate(topic.trim()); }}
        onCancel={() => setConfirmRefresh(false)}
      />
    </div>
  );
}
