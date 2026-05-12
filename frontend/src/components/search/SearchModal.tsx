import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../api/client';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface Props { onClose: () => void; onSynthesize?: (topic: string) => void }

interface SearchResult {
  id: string; content: string; region: string; biome_name: string; planet_name: string;
  confidence: number; context_tags: string[];
}

const REGION_COLORS: Record<string, string> = { analytical: '#7C3AED', procedural: '#0EA5E9', contextual: '#10B981' };

export default function SearchModal({ onClose, onSynthesize }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selected, setSelected] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const trapRef = useFocusTrap<HTMLDivElement>(true);

  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    if (!query.trim()) { setResults([]); setLoading(false); return; }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const res = await apiClient.get<{ records: SearchResult[] }>(`/api/v1/search?query=${encodeURIComponent(query)}&limit=10`);
        setResults(res.records || []);
        setSelected(0);
      } catch (err) { console.error('Search failed:', err); setResults([]); }
      setLoading(false);
    }, 200);
    return () => clearTimeout(t);
  }, [query]);

  const handleKey = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
    else if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(results.length - 1, s + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(0, s - 1)); }
    else if (e.key === 'Enter' && results[selected]) {
      navigate(`/detail/stardust/${results[selected].id}`);
      onClose();
    }
  }, [results, selected, navigate, onClose]);

  function highlight(text: string, q: string): React.ReactNode {
    if (!q.trim()) return text;
    const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    const parts = text.split(re);
    const tester = new RegExp(re.source, 'i');
    return parts.map((part, i) =>
      tester.test(part) ? <mark key={i} className="bg-[rgba(245,158,11,0.22)] text-[#FCD34D] px-0.5 rounded-sm">{part}</mark> : part
    );
  }

  return (
    <div className="absolute inset-0 z-[20] flex flex-col items-center justify-start pt-[14vh] animate-[fade-in_220ms_ease-expo]" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      {/* Scrim */}
      <div className="absolute inset-0 bg-[rgba(7,4,26,0.85)] backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div ref={trapRef} className="relative w-[720px] max-w-[90vw] bg-[rgba(7,4,26,0.96)] border border-[var(--border)] rounded-[14px] shadow-[0_40px_80px_rgba(0,0,0,0.6),0_0_0_1px_rgba(124,58,237,0.15)_inset] overflow-hidden backdrop-blur-[20px] animate-[rise_320ms_ease-expo]" onKeyDown={handleKey} role="dialog" aria-modal="true" aria-label="Search">
        {/* Search bar */}
        <div className="flex items-center gap-3.5 px-5 py-4 border-b border-[var(--border-soft)]">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="1.5"><circle cx="11" cy="11" r="7"/><path d="m20 20-3-3"/></svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your Galaxy..."
            className="flex-1 bg-transparent border-0 outline-none text-[var(--text-1)] font-body text-[17px] placeholder:text-[var(--text-3)]"
            style={{ caretColor: 'var(--violet-300)' }}
          />
          <span className="font-mono text-[10px] text-[var(--text-3)] px-[7px] py-[3px] border border-[var(--border-soft)] rounded bg-[rgba(0,0,0,0.3)]">esc</span>
        </div>

        {/* Scope pills */}
        <div className="flex gap-1.5 px-3.5 py-2.5 border-b border-[var(--border-soft)] bg-[rgba(45,27,105,0.15)]">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] text-[var(--text-1)] bg-[var(--surface-2)] border border-[var(--border-soft)]">
            All <span className="font-mono text-[10px] text-[var(--text-2)]">{results.length}</span>
          </span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] text-[var(--text-3)]">Stardust</span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] text-[var(--text-3)]">Entities</span>
        </div>

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto py-3">
          {query.trim() === '' ? (
            <div className="px-5 py-4 text-xs text-[var(--text-3)]">Start typing to search across your Galaxy...</div>
          ) : loading ? (
            <div className="py-3 space-y-2 px-5">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex items-center gap-3.5 animate-pulse">
                  <span className="w-2 h-2 rounded-full bg-[var(--surface-2)]" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3 bg-[var(--surface-2)] rounded w-3/4" />
                    <div className="h-2.5 bg-[var(--surface-2)] rounded w-1/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : results.length === 0 ? (
            <div className="px-5 py-4 text-xs text-[var(--text-3)]">No results found.</div>
          ) : (
            <>
              <div className="flex items-center justify-between px-5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--text-3)]">
                Results
                <span className="font-mono text-[10px] font-normal tracking-[0.04em] normal-case">{results.length} matches</span>
              </div>
              {results.map((r, i) => (
                <div
                  key={r.id}
                  className={`grid grid-cols-[12px_1fr_auto] gap-3.5 items-center px-5 py-2.5 cursor-pointer transition-colors duration-100 ${i === selected ? 'bg-[rgba(124,58,237,0.18)]' : 'hover:bg-[var(--surface-2)]'}`}
                  onClick={() => { navigate(`/detail/stardust/${r.id}`); onClose(); }}
                  onMouseEnter={() => setSelected(i)}
                >
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: REGION_COLORS[r.region] || '#7C3AED', boxShadow: `0 0 6px ${REGION_COLORS[r.region] || '#7C3AED'}` }} />
                  <div>
                    <div className="text-[13px] text-[var(--text-1)] leading-snug truncate">{highlight(r.content.slice(0, 100), query)}</div>
                    <div className="text-[11px] text-[var(--text-3)] font-mono mt-0.5">{r.region} · {r.biome_name}</div>
                  </div>
                  <div className="flex items-center gap-2.5 flex-shrink-0 text-[11px] text-[var(--text-3)]">
                    <span className="text-[var(--text-2)]">{r.planet_name} / {r.biome_name}</span>
                    <span className="font-mono text-[var(--text-2)]">{r.confidence.toFixed(2)}</span>
                    {i === selected && <span className="font-mono text-[var(--violet-300)]">↵</span>}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--border-soft)] bg-[rgba(45,27,105,0.2)] text-[11px] text-[var(--text-3)]">
          <div className="flex gap-3.5 items-center">
            <span className="flex items-center gap-1.5"><kbd className="font-mono text-[10px] px-1.5 py-0.5 border border-[var(--border-soft)] rounded bg-[rgba(255,255,255,0.04)] text-[var(--text-2)]">↑</kbd><kbd className="font-mono text-[10px] px-1.5 py-0.5 border border-[var(--border-soft)] rounded bg-[rgba(255,255,255,0.04)] text-[var(--text-2)]">↓</kbd> navigate</span>
            <span className="flex items-center gap-1.5"><kbd className="font-mono text-[10px] px-1.5 py-0.5 border border-[var(--border-soft)] rounded bg-[rgba(255,255,255,0.04)] text-[var(--text-2)]">↵</kbd> open</span>
            <span className="flex items-center gap-1.5"><kbd className="font-mono text-[10px] px-1.5 py-0.5 border border-[var(--border-soft)] rounded bg-[rgba(255,255,255,0.04)] text-[var(--text-2)]">esc</kbd> close</span>
          </div>
          <div className="font-mono text-[10px] text-[var(--text-3)] flex items-center gap-2">
            {query.trim() && onSynthesize && (
              <button
                onClick={() => { onSynthesize(query.trim()); onClose(); }}
                className="mr-3 px-2.5 py-1 rounded-full border border-[var(--border-soft)] text-[var(--text-2)] hover:text-[var(--text-1)] hover:border-[var(--violet-300)] transition-all text-[11px] font-sans"
              >Synthesize</button>
            )}
            <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] shadow-[0_0_8px_#34D399] animate-[pulse-dot_2s_ease-in-out_infinite]" />
            Local-only
          </div>
        </div>
      </div>
    </div>
  );
}
