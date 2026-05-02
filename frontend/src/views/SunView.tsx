import React, { useState } from 'react';
import { useSun, useUpdateSunSection, useAddBlocker, useAddDecision, useEvolutionLog, useReimportSteeringDoc } from '../api/sun';
import { Button } from '../components/ui';

const TABS = ['identity', 'values', 'agent_protocol', 'planet_registry', 'working_context', 'steering_doc', 'evolution_log'] as const;
const TAB_LABELS: Record<string, string> = { identity: 'Identity', values: 'Values', agent_protocol: 'Protocol', planet_registry: 'Registry', working_context: 'Working Context', steering_doc: 'Steering Doc', evolution_log: 'Evolution Log' };

export default function SunView() {
  const { data: sun, isLoading } = useSun();
  const { data: evoLog } = useEvolutionLog();
  const updateSection = useUpdateSunSection();
  const addBlocker = useAddBlocker();
  const addDecision = useAddDecision();
  const reimportSteeringDoc = useReimportSteeringDoc();
  const [tab, setTab] = useState<string>('identity');
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const [inlineInput, setInlineInput] = useState('');
  const [inlineMode, setInlineMode] = useState<'blocker' | 'decision' | null>(null);

  if (isLoading || !sun) return <div className="flex items-center justify-center h-screen text-[var(--text-3)]">Loading Sun...</div>;

  const content = sun[tab] || {};

  const startEdit = () => { setEditValue(JSON.stringify(content, null, 2)); setEditing(true); };
  const saveEdit = () => {
    try {
      updateSection.mutate({ key: tab, content: JSON.parse(editValue), summary: `Edited ${tab}` });
      setEditing(false);
    } catch (err) {
      console.error('Sun section save failed:', err);
    }
  };

  const submitInline = () => {
    if (!inlineInput.trim()) return;
    if (inlineMode === 'blocker') addBlocker.mutate(inlineInput);
    else if (inlineMode === 'decision') addDecision.mutate({ decision: inlineInput });
    setInlineInput('');
    setInlineMode(null);
  };

  return (
    <div className="min-h-screen p-8 max-w-4xl mx-auto relative">
      <div className="relative z-[1]">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-8 h-8 rounded-full" style={{
            background: 'radial-gradient(circle at 30% 28%, #FCD34D, #F59E0B 60%, #B45309)',
            boxShadow: '0 0 20px rgba(245, 158, 11, 0.45), inset -3px -4px 8px rgba(0,0,0,0.3)',
          }} />
          <h1 className="font-display text-2xl font-semibold tracking-tight">The Sun</h1>
          <span className="text-[11px] text-[var(--text-3)] font-mono tracking-[0.04em]">steering document</span>
        </div>

        {/* Tabs */}
        <div className="flex gap-1.5 mb-6 flex-wrap">
          {TABS.map(t => (
            <button key={t} onClick={() => { setTab(t); setEditing(false); }}
              className={`px-3 py-1.5 rounded-full text-[11px] font-mono border transition-all duration-150 ${tab === t ? 'bg-[var(--violet-700)] text-white border-[var(--violet-700)]' : 'bg-[var(--surface-3)] text-[var(--text-3)] border-[var(--border-soft)] hover:text-[var(--text-1)] hover:border-[var(--border)]'}`}>
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>

        {/* Content card */}
        <div className="rounded-xl p-6 bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
          {tab === 'steering_doc' ? (
            editing ? (
              <div>
                <textarea value={editValue} onChange={e => setEditValue(e.target.value)} rows={20}
                  className="w-full p-4 rounded-lg bg-[var(--surface-3)] border border-[var(--border-soft)] font-mono text-[13px] text-[var(--text-1)] outline-none focus:border-[var(--violet-300)] transition-colors duration-150" />
                <div className="flex gap-2 mt-4">
                  <Button variant="primary" onClick={() => {
                    updateSection.mutate({ key: 'steering_doc', content: { ...content, markdown: editValue }, summary: 'Edited steering doc' });
                    setEditing(false);
                  }}>Save</Button>
                  <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
                </div>
              </div>
            ) : (
              <div>
                <pre className="whitespace-pre-wrap text-[13px] text-[var(--text-1)] font-mono leading-relaxed">{(content as any)?.markdown || ''}</pre>
                {(content as any)?.source_path && (
                  <p className="mt-4 text-[11px] text-[var(--text-3)] font-mono">Source: {(content as any).source_path}</p>
                )}
                <div className="mt-6 flex gap-2">
                  <Button variant="ghost" onClick={() => { setEditValue((content as any)?.markdown || ''); setEditing(true); }}>Edit</Button>
                  {(content as any)?.source_path && (
                    <Button variant="ghost" onClick={() => reimportSteeringDoc.mutate()}>
                      {reimportSteeringDoc.isPending ? 'Re-importing...' : 'Re-import from file'}
                    </Button>
                  )}
                </div>
              </div>
            )
          ) : tab === 'evolution_log' ? (
            <div className="space-y-2">
              <h2 className="font-display text-sm font-medium mb-4">Change History</h2>
              {(evoLog || []).slice().reverse().map((e: { timestamp?: string; section_changed?: string; changed_by?: string; summary?: string }, i: number) => (
                <div key={i} className="flex gap-3 text-xs border-l-2 border-[rgba(124,58,237,0.3)] pl-3 py-1">
                  <span className="text-[var(--text-3)] w-36 shrink-0 font-mono text-[11px]">{e.timestamp?.slice(0, 16)}</span>
                  <span className="text-[var(--violet-300)] font-mono text-[11px]">{e.section_changed}</span>
                  <span className="text-[var(--text-3)] font-mono text-[11px]">by {e.changed_by}</span>
                  <span className="flex-1 text-[var(--text-1)]">{e.summary}</span>
                </div>
              ))}
              {(!evoLog || evoLog.length === 0) && <p className="text-[var(--text-3)] text-xs">No changes recorded yet.</p>}
            </div>
          ) : editing ? (
            <div>
              <textarea value={editValue} onChange={e => setEditValue(e.target.value)} rows={16}
                className="w-full p-4 rounded-lg bg-[var(--surface-3)] border border-[var(--border-soft)] font-mono text-[13px] text-[var(--text-1)] outline-none focus:border-[var(--violet-300)] transition-colors duration-150" />
              <div className="flex gap-2 mt-4">
                <Button variant="primary" onClick={saveEdit}>Save</Button>
                <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div>
              <div className="space-y-2">
                {typeof content === 'object' && Object.entries(content).map(([k, v]) => (
                  <div key={k} className="flex gap-4 py-1.5 border-b border-[var(--border-soft)] last:border-0">
                    <span className="text-[var(--text-3)] w-48 shrink-0 text-xs font-mono">{k}</span>
                    <span className="text-xs text-[var(--text-1)]">
                      {Array.isArray(v) ? (v as unknown[]).map((item, i) => (
                        <div key={i} className="py-0.5">• {typeof item === 'object' ? JSON.stringify(item) : String(item)}</div>
                      )) : String(v)}
                    </span>
                  </div>
                ))}
              </div>

              {tab === 'working_context' && (
                <div className="mt-6 flex gap-2">
                  <button onClick={() => setInlineMode('blocker')} className="px-3 py-1.5 bg-[rgba(245,158,11,0.1)] text-[var(--warning)] rounded-lg text-xs border border-[rgba(245,158,11,0.3)] hover:bg-[rgba(245,158,11,0.15)] transition-colors duration-150">+ Add blocker</button>
                  <button onClick={() => setInlineMode('decision')} className="px-3 py-1.5 bg-[rgba(124,58,237,0.1)] text-[var(--violet-300)] rounded-lg text-xs border border-[rgba(124,58,237,0.3)] hover:bg-[rgba(124,58,237,0.15)] transition-colors duration-150">+ Add decision</button>
                </div>
              )}

              {inlineMode && (
                <div className="mt-3 flex gap-2">
                  <input value={inlineInput} onChange={e => setInlineInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && submitInline()}
                    placeholder={inlineMode === 'blocker' ? 'New blocker...' : 'New decision...'} autoFocus
                    className="flex-1 h-9 px-3 rounded-lg bg-[var(--surface-3)] border border-[var(--border-soft)] text-[var(--text-1)] font-body text-[13px] outline-none focus:border-[var(--violet-300)] transition-colors duration-150 placeholder:text-[var(--text-3)]" />
                  <Button variant="primary" onClick={submitInline}>Add</Button>
                  <Button variant="ghost" onClick={() => setInlineMode(null)} aria-label="Close">×</Button>
                </div>
              )}

              <div className="mt-6">
                <Button variant="ghost" onClick={startEdit}>Edit section</Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
