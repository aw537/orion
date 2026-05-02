import React, { useState } from 'react';
import { useAgents, useAgentExpertise, useAgentHealth, AgentIdentity } from '../../api/agents';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { Panel } from '../ui';

function ExpertiseBar({ domain, level }: { domain: string; level: number }) {
  const pct = Math.round(level * 100);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-24 truncate text-[var(--text-2)]">{domain}</span>
      <div className="flex-1 h-1.5 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden">
        <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-400" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right font-mono text-[var(--text-3)]">{level.toFixed(2)}</span>
    </div>
  );
}

function AgentCard({ agent, onClick }: { agent: AgentIdentity; onClick: () => void }) {
  return (
    <div onClick={onClick} className="p-3 rounded-lg bg-[rgba(45,27,105,0.3)] border border-[var(--border-soft)] cursor-pointer hover:border-[var(--border)] transition-all duration-150">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34D399]" />
        <span className="text-sm font-medium text-[var(--text-1)]">{agent.agent_name}</span>
      </div>
      <div className="text-xs text-[var(--text-3)]">
        {agent.current_model} · Session {agent.total_sessions}
      </div>
    </div>
  );
}

function AgentDetail({ name, onClose }: { name: string; onClose: () => void }) {
  const { data: expertise } = useAgentExpertise(name);
  const { data: health } = useAgentHealth(name);

  const healthColor = (health?.overall_health ?? 0) >= 0.8 ? 'text-emerald-400' : (health?.overall_health ?? 0) >= 0.6 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-1)]">{name}</h3>
        <button onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--text-1)] text-xs" aria-label="Close">&times;</button>
      </div>

      {health && (
        <div className="text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-[var(--text-2)]">Brain Health</span>
            <span className={healthColor}>{health.overall_health.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-3)]">Freshness</span>
            <span className="text-[var(--text-2)]">{health.knowledge_freshness.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--text-3)]">Age</span>
            <span className="text-[var(--text-2)]">{health.brain_age_days} days</span>
          </div>
        </div>
      )}

      {expertise && Array.isArray(expertise) && expertise.length > 0 && (
        <div className="space-y-1.5">
          <h4 className="text-xs font-medium text-[var(--text-2)]">Expertise</h4>
          {expertise.slice(0, 5).map(e => <ExpertiseBar key={e.domain} domain={e.domain} level={e.level} />)}
        </div>
      )}

      {health?.recommended_enrichment && health.recommended_enrichment.length > 0 && (
        <div className="space-y-1">
          <h4 className="text-xs font-medium text-amber-400">Recommendations</h4>
          {health.recommended_enrichment.map((r, i) => (
            <p key={i} className="text-xs text-[var(--text-3)]">→ {r}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AgentPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: agents } = useAgents();
  const [selected, setSelected] = useState<string | null>(null);
  const trapRef = useFocusTrap<HTMLDivElement>(open);

  if (!open) return null;

  return (
    <Panel ref={trapRef} width="sm" className="overflow-y-auto">
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-[var(--text-1)]">Agents</h2>
          <button onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--text-1)]" aria-label="Close">&times;</button>
        </div>

        {selected ? (
          <AgentDetail name={selected} onClose={() => setSelected(null)} />
        ) : (
          <div className="space-y-2">
            {agents?.map(a => <AgentCard key={a.id} agent={a} onClick={() => setSelected(a.agent_name)} />)}
            {(!agents || agents.length === 0) && <p className="text-xs text-[var(--text-3)]">No agents have connected yet. Connect one via MCP to get started.</p>}
          </div>
        )}
      </div>
    </Panel>
  );
}
