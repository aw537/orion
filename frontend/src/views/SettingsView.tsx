import React from 'react';
import { useModelProfiles, useCacheTTLConfig } from '../api/dashboard';

const formatDuration = (seconds: number) => {
  if (seconds >= 86400) return `${Math.round(seconds / 86400)}d`;
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 60)}m`;
};

export default function SettingsView() {
  const { data: profiles } = useModelProfiles();
  const { data: cacheCfg } = useCacheTTLConfig();

  return (
    <div className="min-h-screen p-8 max-w-4xl mx-auto relative">
      <div className="relative z-[1]">
        <h1 className="font-display text-2xl font-semibold tracking-tight mb-8">Settings</h1>

        {/* Model Profiles */}
        <section className="mb-10">
          <h2 className="font-display text-base font-medium mb-4">Model Profiles</h2>
          <div className="space-y-1.5">
            {(profiles || []).map((p: { id: string; display_name: string; model_id: string; context_window_tokens: number; optimal_context_tokens: number; format_preference: string; tool_calling: string; is_builtin: boolean }) => (
              <div key={p.id} className="flex items-center gap-4 p-3.5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)] hover:bg-[var(--surface-2)] transition-colors duration-150">
                <span className="font-medium text-[var(--text-1)] text-sm w-40">{p.display_name}</span>
                <span className="text-[11px] text-[var(--text-3)] font-mono w-32">{p.model_id}</span>
                <span className="text-[11px] text-[var(--text-3)] font-mono">ctx: {(p.context_window_tokens / 1000).toFixed(0)}k</span>
                <span className="text-[11px] text-[var(--text-3)] font-mono">optimal: {(p.optimal_context_tokens / 1000).toFixed(0)}k</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--surface-3)] border border-[var(--border-soft)] text-[var(--text-2)] font-mono">{p.format_preference}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--surface-3)] border border-[var(--border-soft)] text-[var(--text-2)] font-mono">{p.tool_calling}</span>
                {p.is_builtin
                  ? <span className="text-[10px] text-[var(--text-3)] font-mono">built-in</span>
                  : <span className="text-[10px] text-[#34D399] font-mono">custom</span>}
              </div>
            ))}
          </div>
        </section>

        {/* Cache TTL Config */}
        <section>
          <h2 className="font-display text-base font-medium mb-4">Cache TTL per Region</h2>
          <div className="space-y-1.5">
            {cacheCfg && Object.entries(cacheCfg.defaults || {}).map(([region, seconds]) => (
              <div key={region} className="flex items-center gap-4 p-3.5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
                <span className="font-medium text-[var(--text-1)] text-sm w-28 capitalize">{region}</span>
                <div className="flex-1 h-1.5 bg-[var(--surface-3)] rounded-full overflow-hidden border border-[var(--border-soft)]">
                  <div className="h-full bg-[var(--violet-700)] rounded-full" style={{ width: `${Math.min(100, ((seconds as number) / 604800) * 100)}%` }} />
                </div>
                <span className="text-sm text-[var(--text-2)] font-mono w-12 text-right">{formatDuration(seconds as number)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
