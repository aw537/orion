import React, { useState } from 'react';
import { useGalaxyStrength, useGalaxyStatus } from '../../api/galaxy';
import { apiClient } from '../../api/client';
import { Button, Panel } from '../ui';

interface Props { open: boolean; onClose: () => void }

export default function SunPanel({ open, onClose }: Props) {
  const { data: strength } = useGalaxyStrength();
  const { data: status } = useGalaxyStatus();
  const [auditRunning, setAuditRunning] = useState(false);

  const runAudit = async () => {
    setAuditRunning(true);
    try {
      await apiClient.post('/api/v1/audit/run');
    } catch (err) {
      console.error('Audit run failed:', err);
    } finally {
      setAuditRunning(false);
    }
  };

  const planets: { name: string; color: string; count: number }[] = status?.planets?.map((p: { name: string; color?: string; stardust_count?: number }) => ({
    name: p.name,
    color: p.color || '#7C3AED',
    count: p.stardust_count || 0,
  })) ?? [];

  const totalDust = planets.reduce((s, p) => s + p.count, 0) || 1;

  return (
    <Panel width="md" open={open}>
      <header className="px-7 pt-6 pb-5 border-b border-[var(--border-soft)] flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-full flex-shrink-0"
            style={{
              background: 'radial-gradient(circle at 30% 28%, #FCD34D, #F59E0B 60%, #B45309)',
              boxShadow: '0 0 20px rgba(245, 158, 11, 0.55), inset -4px -6px 10px rgba(0,0,0,0.35)',
            }}
          />
          <div>
            <h2 className="font-display text-base font-medium leading-snug">The Sun</h2>
            <div className="text-[11px] text-[var(--text-3)] font-mono tracking-[0.04em]">Galaxy core · all-parent node</div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-full border border-[var(--border-soft)] bg-transparent text-[var(--text-2)] flex items-center justify-center hover:text-[var(--text-1)] hover:border-[var(--border)] transition-colors duration-150 flex-shrink-0"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-7 pt-5 pb-7">
        {/* Stats grid */}
        <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--text-3)] mb-2.5">Galaxy at a glance</div>
        <div className="grid grid-cols-2 gap-2.5">
          {[
            { l: 'Strength', v: Math.round(strength?.score ?? 0).toLocaleString(), sub: strength?.trend || '' },
            { l: 'Stardust', v: (status?.total_stardust ?? 0).toLocaleString(), sub: '' },
            { l: 'Entities', v: (status?.total_entities ?? 0).toLocaleString(), sub: '' },
            { l: 'Planets', v: (status?.planets?.length ?? 0).toString(), sub: 'stable' },
          ].map((s) => (
            <div key={s.l} className="bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)] p-3 rounded-[10px]">
              <div className="text-[10px] text-[var(--text-3)] uppercase tracking-[0.08em]">{s.l}</div>
              <div className="font-mono text-lg text-[var(--text-1)] mt-1 leading-none">{s.v}</div>
              {s.sub && <div className="font-mono text-[10px] text-[#34D399] mt-1">{s.sub}</div>}
            </div>
          ))}
        </div>

        {/* Composition */}
        {planets.length > 0 && (
          <>
            <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--text-3)] mt-5 mb-2.5">Composition</div>
            <div className="flex h-2 rounded-full overflow-hidden gap-px">
              {planets.map((p) => (
                <div
                  key={p.name}
                  style={{ flex: p.count / totalDust, background: p.color, opacity: 0.85 }}
                  title={`${p.name}: ${p.count.toLocaleString()}`}
                />
              ))}
            </div>
            <div className="mt-3 space-y-2">
              {planets.map((p) => (
                <div key={p.name} className="flex items-center gap-2.5 text-xs">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color, boxShadow: `0 0 6px ${p.color}` }} />
                  <span className="text-[var(--text-2)] flex-1 truncate">{p.name}</span>
                  <span className="font-mono text-[11px] text-[var(--text-3)]">{Math.round((p.count / totalDust) * 100)}%</span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Contradictions */}
        <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--text-3)] mt-5 mb-2.5">Contradictions</div>
        <div className="flex items-center gap-2.5 p-3 bg-[rgba(245,158,11,0.06)] border border-[rgba(245,158,11,0.2)] rounded-[10px]">
          <span className="w-2 h-2 rounded-full bg-[#F59E0B] shadow-[0_0_6px_#F59E0B] flex-shrink-0" />
          <span className="text-xs text-[var(--text-1)]">
            {status?.contradiction_count_unresolved ?? 0} unresolved
          </span>
        </div>

        {/* Audit info */}
        {status?.last_audit && (
          <>
            <div className="text-[10px] uppercase tracking-[0.1em] text-[var(--text-3)] mt-5 mb-1.5">Last audit</div>
            <div className="font-mono text-[11px] text-[var(--text-3)]">{status.last_audit}</div>
          </>
        )}

        <div className="flex flex-col gap-2 mt-5">
          <Button variant="secondary" onClick={runAudit} disabled={auditRunning}>{auditRunning ? 'Running...' : 'Run audit now'}</Button>
          <Button variant="ghost" onClick={() => alert('Export Galaxy snapshot coming soon')}>Export Galaxy snapshot</Button>
        </div>
      </div>
    </Panel>
  );
}
