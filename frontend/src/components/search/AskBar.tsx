import React, { useState, useRef, useEffect } from 'react';
import { askBrain, type AskResult } from '../../api/brain';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface Props {
  onClose: () => void;
  onSynthesize?: (topic: string) => void;
}

const INTENT_LABELS: Record<string, { icon: string; label: string }> = {
  expertise_query: { icon: '', label: 'Expertise' },
  decision_query: { icon: '', label: 'Decisions' },
  connection_query: { icon: '', label: 'Connection' },
  neighborhood_query: { icon: '', label: 'Neighborhood' },
  synthesis_query: { icon: '', label: 'Synthesis' },
};

export default function AskBar({ onClose, onSynthesize }: Props) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const trapRef = useFocusTrap<HTMLDivElement>(true);

  useEffect(() => { inputRef.current?.focus(); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await askBrain(query.trim());
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Failed to ask');
    }
    setLoading(false);
  }

  const intent = result ? INTENT_LABELS[result.intent] || INTENT_LABELS.synthesis_query : null;

  return (
    <div className="absolute inset-0 z-[20] flex flex-col items-center justify-start pt-[12vh]" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="absolute inset-0 bg-[rgba(7,4,26,0.85)] backdrop-blur-sm" onClick={onClose} />

      <div ref={trapRef} className="relative w-full max-w-[640px] z-[21]" role="dialog" aria-modal="true" aria-label="Ask your Galaxy">
        {/* Input */}
        <form onSubmit={handleSubmit}>
          <div className="flex items-center gap-3 bg-[rgba(15,10,40,0.95)] border border-[var(--border)] rounded-2xl px-5 py-3.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
            <span className="text-lg">*</span>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask your Galaxy anything..."
              className="flex-1 bg-transparent text-[var(--text-1)] text-sm outline-none placeholder:text-[var(--text-3)]"
              onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
            />
            {loading ? (
              <span className="text-xs text-[var(--text-3)] animate-pulse">Thinking...</span>
            ) : (
              <button type="submit" className="text-xs text-[var(--accent)] hover:text-[var(--text-1)] transition-colors">
                Ask ↵
              </button>
            )}
          </div>
        </form>

        {/* Error */}
        {error && (
          <div className="mt-3 px-5 py-3 bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.3)] rounded-xl text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="mt-3 bg-[rgba(15,10,40,0.95)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
            {/* Intent badge */}
            <div className="flex items-center gap-2 px-5 py-2.5 border-b border-[var(--border-soft)]">
              <span>{intent?.icon}</span>
              <span className="text-xs font-medium text-[var(--accent)]">{intent?.label}</span>
              {result.confidence != null && (
                <span className="ml-auto text-xs text-[var(--text-3)]">{Math.round(result.confidence * 100)}% confidence</span>
              )}
            </div>

            {/* Answer */}
            <div className="px-5 py-4 text-sm text-[var(--text-1)] leading-relaxed whitespace-pre-wrap">
              {result.answer || 'No answer found.'}
            </div>

            {/* Key decisions */}
            {result.key_decisions && result.key_decisions.length > 0 && (
              <div className="px-5 pb-3">
                <div className="text-xs font-medium text-[var(--text-2)] mb-1.5">Key decisions</div>
                {result.key_decisions.map((d, i) => (
                  <div key={i} className="text-xs text-[var(--text-2)] py-1 pl-3 border-l-2 border-[var(--accent)] mb-1">{d}</div>
                ))}
              </div>
            )}

            {/* Open questions */}
            {result.open_questions && result.open_questions.length > 0 && (
              <div className="px-5 pb-3">
                <div className="text-xs font-medium text-[var(--text-2)] mb-1.5">Open questions</div>
                {result.open_questions.map((q, i) => (
                  <div key={i} className="text-xs text-[var(--text-3)] py-1">• {q}</div>
                ))}
              </div>
            )}

            {/* Supporting records */}
            {result.supporting_records && result.supporting_records.length > 0 && (
              <div className="px-5 pb-4 border-t border-[var(--border-soft)] pt-3">
                <div className="text-xs font-medium text-[var(--text-3)] mb-2">
                  Based on {result.supporting_records.length} record{result.supporting_records.length !== 1 ? 's' : ''}
                </div>
                {result.supporting_records.slice(0, 3).map((r: any, i: number) => (
                  <div key={i} className="text-xs text-[var(--text-2)] py-1.5 border-b border-[var(--border-soft)] last:border-0 truncate">
                    {r.content?.slice(0, 120)}
                  </div>
                ))}
              </div>
            )}

            {/* Synthesize action */}
            {onSynthesize && (
              <div className="px-5 py-2.5 border-t border-[var(--border-soft)] flex justify-end">
                <button
                  onClick={() => { onSynthesize(query); onClose(); }}
                  className="text-xs text-[var(--accent)] hover:text-[var(--text-1)] transition-colors"
                >
                  Deep synthesize →
                </button>
              </div>
            )}
          </div>
        )}

        {/* Hints */}
        {!result && !loading && (
          <div className="mt-4 px-2 flex flex-wrap gap-2">
            {['Who knows about auth?', 'What decisions were made about the database?', 'Everything about FastAPI'].map((hint) => (
              <button
                key={hint}
                onClick={() => { setQuery(hint); }}
                className="text-xs text-[var(--text-3)] px-3 py-1.5 rounded-full border border-[var(--border-soft)] hover:border-[var(--border)] hover:text-[var(--text-2)] transition-all"
              >
                {hint}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
