import React, { useState } from 'react';
import { useStardust } from '../../api/stardust';
import { apiClient } from '../../api/client';
import { useQueryClient } from '@tanstack/react-query';
import { Button, Panel } from '../ui';

const REGION_COLORS: Record<string, string> = { analytical: '#7C3AED', procedural: '#0EA5E9', contextual: '#10B981' };

interface Props {
  stardustId: string;
  onClose: () => void;
}

export default function StardustDetail({ stardustId, onClose }: Props) {
  const { data: sd } = useStardust(stardustId);
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  React.useEffect(() => { if (sd) setContent(sd.content); }, [sd]);

  if (!sd) return null;

  const regionColor = REGION_COLORS[sd.region] || '#7C3AED';
  const confColor = sd.confidence >= 0.8 ? '#34D399' : sd.confidence >= 0.5 ? '#F59E0B' : '#9CA3AF';

  const handleSave = async () => {
    setError(null);
    try {
      await apiClient.put(`/api/v1/stardust/${stardustId}`, { content });
      qc.invalidateQueries({ queryKey: ['stardust', stardustId] });
      setEditing(false);
    } catch (err) {
      setError((err as Error).message || 'Failed to save. Please try again.');
    }
  };

  return (
    <Panel width="lg" className="z-[8]">
      {/* Header */}
      <header className="px-5 pt-4 pb-4 border-b border-[var(--border-soft)] flex items-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-[5px] px-[9px] py-[3px] rounded-full text-[10px] font-semibold tracking-[0.08em] uppercase border"
          style={{ color: regionColor, background: `${regionColor}26`, borderColor: `${regionColor}55` }}>
          <span className="w-[5px] h-[5px] rounded-full bg-current" />
          {sd.region}
        </span>
        <span className="inline-flex items-center gap-[5px] px-[9px] py-[3px] rounded-full text-[10px] font-semibold tracking-[0.08em] uppercase border border-[var(--border-soft)] bg-[var(--surface-3)] text-[var(--text-2)]">
          ⌖ {sd.gravity}
        </span>
        {sd.contradiction_id && (
          <span className="inline-flex items-center gap-[5px] px-[9px] py-[3px] rounded-full text-[10px] font-semibold tracking-[0.08em] uppercase border border-[rgba(245,158,11,0.4)] bg-[rgba(245,158,11,0.12)] text-[#FCD34D]">
            <span className="w-[5px] h-[5px] rounded-full bg-current" />
            Conflict
          </span>
        )}
        <div className="ml-auto flex items-center gap-3">
          <div className="inline-flex items-center gap-2 font-mono text-xs text-[var(--text-1)]">
            <span className="w-2 h-2 rounded-full" style={{ background: confColor, boxShadow: `0 0 6px ${confColor}` }} />
            {sd.confidence.toFixed(2)}
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-full border border-[var(--border-soft)] bg-transparent text-[var(--text-2)] flex items-center justify-center hover:text-[var(--text-1)] hover:border-[var(--border)]" aria-label="Close">×</button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        {/* Content */}
        <section className="px-5 py-5 border-b border-[var(--border-soft)] relative">
          <div className="absolute top-5 right-5 flex gap-1.5 items-center z-[2]">
            {editing && <div className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] shadow-[0_0_6px_#F59E0B]" />}
            <button
              onClick={() => setEditing(!editing)}
              className={`w-[26px] h-[26px] rounded-md border flex items-center justify-center cursor-pointer transition-colors duration-150 ${editing ? 'border-[rgba(245,158,11,0.5)] text-[#FCD34D] bg-[rgba(245,158,11,0.12)]' : 'border-[var(--border-soft)] text-[var(--violet-300)] bg-[rgba(124,58,237,0.12)] hover:bg-[rgba(124,58,237,0.22)]'}`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
          </div>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            readOnly={!editing}
            className={`w-full min-h-[220px] font-body text-sm leading-[1.7] text-[var(--text-1)] bg-transparent border rounded-md p-1.5 -m-1.5 resize-none outline-none transition-all duration-150 ${editing ? 'border-[rgba(245,158,11,0.4)] bg-[rgba(245,158,11,0.05)]' : 'border-transparent'}`}
          />
          {error && <p className="text-xs text-red-400 mt-3">{error}</p>}
          {editing && (
            <div className="flex gap-2.5 items-center mt-4">
              <Button variant="primary" onClick={handleSave}>Save changes</Button>
              <Button variant="ghost" onClick={() => { setEditing(false); setContent(sd.content); setError(null); }}>Cancel</Button>
              <span className="text-[11px] text-[var(--text-3)]">Edits create a HUMAN_EDIT log entry.</span>
            </div>
          )}
        </section>

        {/* Metadata */}
        <section className="px-5 py-5 border-b border-[var(--border-soft)]">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-3 flex items-center justify-between">
            Metadata <span className="font-mono font-normal text-[11px] tracking-normal normal-case">{sd.id.slice(0, 8)}</span>
          </h3>
          <dl className="grid grid-cols-[110px_1fr] gap-x-4 gap-y-2.5 text-xs">
            <dt className="text-[var(--text-3)]">Source</dt>
            <dd className="font-mono text-[var(--text-1)]">{sd.source_agent || 'unknown'}</dd>
            <dt className="text-[var(--text-3)]">Created</dt>
            <dd className="font-mono text-[var(--text-1)]">{new Date(sd.created_at).toLocaleDateString()}</dd>
            <dt className="text-[var(--text-3)]">Accessed</dt>
            <dd className="font-mono text-[var(--text-1)]">{sd.access_count} times</dd>
            {sd.context_tags?.length > 0 && (
              <>
                <dt className="text-[var(--text-3)]">Tags</dt>
                <dd className="flex gap-1.5 flex-wrap">
                  {sd.context_tags.map((t: string) => (
                    <span key={t} className="px-2 py-px bg-[var(--surface-3)] border border-[var(--border-soft)] rounded-full text-[11px] text-[var(--text-2)]">{t}</span>
                  ))}
                </dd>
              </>
            )}
          </dl>

          {/* Confidence sparkline */}
          <div className="mt-4">
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)]">Confidence history</span>
              <span className="font-mono text-[11px] text-[var(--text-2)]">90 days</span>
            </div>
            <svg className="w-full h-14 block" viewBox="0 0 380 56" preserveAspectRatio="none">
              <defs>
                <linearGradient id="sg" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#34D399" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#34D399" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M 0 36 L 22 38 L 44 32 L 66 36 L 88 30 L 110 28 L 132 32 L 154 24 L 176 22 L 198 26 L 220 18 L 242 16 L 264 20 L 286 14 L 308 10 L 330 12 L 352 8 L 380 6 L 380 56 L 0 56 Z" fill="url(#sg)" opacity="0.7" />
              <path d="M 0 36 L 22 38 L 44 32 L 66 36 L 88 30 L 110 28 L 132 32 L 154 24 L 176 22 L 198 26 L 220 18 L 242 16 L 264 20 L 286 14 L 308 10 L 330 12 L 352 8 L 380 6" fill="none" stroke="#34D399" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" style={{ strokeDasharray: 380, strokeDashoffset: 380, animation: 'spark-draw 600ms var(--ease-out-expo) 200ms forwards' }} />
              <circle cx="380" cy="6" r="3" fill="#34D399" />
            </svg>
          </div>
        </section>

        {/* Contradiction */}
        {sd.contradiction_id && (
          <section className="px-5 py-5 border-b border-[var(--border-soft)]">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-3">Contradiction</h3>
            <div className="border border-[rgba(245,158,11,0.4)] bg-[rgba(245,158,11,0.06)] rounded-[10px] p-4">
              <div className="flex items-center gap-2 mb-2.5">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#FCD34D" strokeWidth="1.6"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                <strong className="font-display text-[13px] font-semibold text-[#FCD34D]">Contradiction detected</strong>
              </div>
              <div className="text-xs text-[var(--text-1)] mb-3.5 leading-relaxed">
                This record conflicts with another record in this Biome.
              </div>
              <div className="text-[11px] text-[var(--text-3)] uppercase tracking-[0.08em] mb-2">Resolve as</div>
              <div className="flex gap-2 flex-wrap">
                <button className="px-3 py-2 bg-transparent border border-[var(--border-soft)] border-l-[3px] border-l-[#34D399] rounded-md text-[var(--text-1)] text-xs cursor-pointer hover:bg-[var(--surface-2)] transition-colors duration-150">Coexist</button>
                <button className="px-3 py-2 bg-transparent border border-[var(--border-soft)] border-l-[3px] border-l-[var(--violet-300)] rounded-md text-[var(--text-1)] text-xs cursor-pointer hover:bg-[var(--surface-2)] transition-colors duration-150">Supersedes</button>
                <button className="px-3 py-2 bg-transparent border border-[var(--border-soft)] border-l-[3px] border-l-[#FCD34D] rounded-md text-[var(--text-1)] text-xs cursor-pointer hover:bg-[var(--surface-2)] transition-colors duration-150">Temporal</button>
              </div>
            </div>
          </section>
        )}
      </div>
    </Panel>
  );
}
