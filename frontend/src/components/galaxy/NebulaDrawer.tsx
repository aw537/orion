import React, { useState } from 'react';
import { useNebulaStore } from '../../store/nebulaStore';

const ACTION_COLORS: Record<string, string> = {
  WRITE: '#A78BFA', READ: '#38BDF8', ENTITY_EXTRACTED: '#EC4899', ENTITY_ENRICHED: '#EC4899',
  CONTRADICTION_DETECTED: '#F59E0B', CONTRADICTION_RESOLVED: '#34D399', HUMAN_EDIT: '#F59E0B', AUDIT_RUN: '#9CA3AF',
  PROMOTE: '#34D399', SESSION_START: '#34D399', SESSION_END: '#9CA3AF', SESSION_SUMMARY: '#C4B5FD',
  SYNTHESIS_GENERATED: '#818CF8',
  PLANET_ROUTED: '#10B981', INBOX_ROUTED: '#F59E0B', INBOX_RESOLVED: '#6D28D9',
};

function timeAgo(ts: string): string {
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

function SummaryCard({ event }: { event: any }) {
  const [expanded, setExpanded] = useState(false);
  const d = event;
  return (
    <div
      className="mx-6 my-2 p-3.5 bg-[rgba(124,58,237,0.1)] border border-[rgba(196,181,253,0.25)] rounded-lg cursor-pointer transition-all duration-200 hover:bg-[rgba(124,58,237,0.15)]"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[#C4B5FD] flex items-center gap-2">
          Session Summary
          <span className="text-[var(--text-3)] font-mono text-[11px]">{d.initiated_by}</span>
        </span>
        <span className="text-[var(--text-3)] font-mono text-[11px]" title={d.timestamp || ''}>{d.timestamp ? timeAgo(d.timestamp) : ''}</span>
      </div>
      <div className="flex gap-4 mt-2 text-[11px] text-[var(--text-2)]">
        <span>✏️ {d.records_written ?? '?'} written</span>
        <span>🔗 {d.entities_enriched ?? 0} enriched</span>
        {(d.strength_delta ?? 0) !== 0 && <span className={d.strength_delta > 0 ? 'text-[#34D399]' : 'text-[#F87171]'}>{d.strength_delta > 0 ? '+' : ''}{d.strength_delta}</span>}
      </div>
      {expanded && (
        <div className="mt-3 pt-3 border-t border-[var(--border-soft)] text-[11px] text-[var(--text-2)] space-y-1.5">
          {d.top_topics?.length > 0 && <div>Topics: {d.top_topics.join(', ')}</div>}
          {d.tier_upgrades?.length > 0 && (
            <div>{d.tier_upgrades.map((u: any, i: number) => <span key={i} className="text-[#FCD34D]">⬆ {u.name} T{u.from}→T{u.to} </span>)}</div>
          )}
          {d.contradictions_detected > 0 && <div className="text-[#F59E0B]">{d.contradictions_detected} contradictions detected</div>}
          <div className="text-[var(--text-3)]">{d.duration_minutes}min · {d.strength_before}→{d.strength_after}</div>
        </div>
      )}
    </div>
  );
}

interface Props { open: boolean; onClose: () => void }

export default function NebulaDrawer({ open, onClose }: Props) {
  const events = useNebulaStore((s) => s.events);

  return (
    <div
      className="absolute left-0 right-0 bottom-0 z-[8] bg-[rgba(7,4,26,0.95)] backdrop-blur-[20px] border-t border-[var(--border)] flex flex-col pointer-events-auto transition-transform duration-[360ms] ease-expo"
      style={{ height: '40vh', minHeight: 320, transform: open ? 'translateY(0)' : 'translateY(100%)' }}
    >
      <div className="flex items-center justify-between px-8 py-4 border-b border-[var(--border-soft)]">
        <h2 className="font-display text-base font-medium flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-[#34D399] shadow-[0_0_8px_#34D399] animate-[pulse-dot_2s_ease-in-out_infinite]" />
          Nebula · live activity
        </h2>
        <button onClick={onClose} aria-label="Close" className="w-8 h-8 rounded-full bg-transparent border border-[var(--border-soft)] text-[var(--text-2)] flex items-center justify-center hover:text-[var(--text-1)] hover:border-[var(--border)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        {events.length === 0 && <p className="text-xs text-[var(--text-3)] px-8 py-4">No events yet...</p>}
        {events.map((e) =>
          e.action_type === 'SESSION_SUMMARY' ? (
            <SummaryCard key={e.event_id} event={e} />
          ) : (
            <div key={e.event_id} className="grid grid-cols-[130px_1fr_auto] gap-3.5 items-center px-8 py-2.5 text-xs hover:bg-[var(--surface-2)] transition-colors duration-100">
              <span className="font-mono text-[11px] tracking-[0.06em]" style={{ color: ACTION_COLORS[e.action_type] || '#9CA3AF' }}>
                {e.action_type}
              </span>
              <span className="text-[var(--text-1)]">
                {e.record_id || e.biome_id || ''}
                <span className="text-[var(--text-3)] ml-2 font-mono text-[11px]">{e.initiated_by}</span>
              </span>
              <span className="text-[var(--text-3)] font-mono text-[11px]" title={e.timestamp || ''}>{e.timestamp ? timeAgo(e.timestamp) : ''}</span>
            </div>
          )
        )}
      </div>
    </div>
  );
}
