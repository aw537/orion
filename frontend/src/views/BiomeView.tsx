import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useBiome, useBiomeStardust } from '../api/biomes';
import BiomeGraph from '../components/biome/BiomeGraph';
import SynthesisPanel from '../components/search/SynthesisPanel';

const REGION_COLORS: Record<string, string> = {
  analytical: '#7C3AED',
  procedural: '#0EA5E9',
  contextual: '#10B981',
  creative: '#F59E0B',
  empathetic: '#EC4899',
  critical: '#EF4444',
  strategic: '#6366F1',
};

const REGIONS = [
  { key: 'analytical', label: 'Analytical', color: '#7C3AED' },
  { key: 'procedural', label: 'Procedural', color: '#0EA5E9' },
  { key: 'contextual', label: 'Contextual', color: '#10B981' },
  { key: 'creative', label: 'Creative', color: '#F59E0B' },
  { key: 'empathetic', label: 'Empathetic', color: '#EC4899' },
  { key: 'critical', label: 'Critical', color: '#EF4444' },
  { key: 'strategic', label: 'Strategic', color: '#6366F1' },
];

export default function BiomeView() {
  const { biomeId } = useParams<{ biomeId: string }>();
  const { data: biome, isLoading } = useBiome(biomeId!);
  const { data: stardustPage } = useBiomeStardust(biomeId!);
  const navigate = useNavigate();
  const [activeRegion, setActiveRegion] = useState<string | null>(null);
  const [view, setView] = useState<'records' | 'graph'>('records');
  const [synthesisOpen, setSynthesisOpen] = useState(false);

  if (isLoading || !biome) return <div className="flex items-center justify-center h-screen text-[var(--text-3)]">Loading Biome...</div>;

  const allRecords: any[] = stardustPage?.items ?? [];
  const records = activeRegion ? allRecords.filter((r: any) => r.region === activeRegion) : allRecords;

  return (
    <div className="h-full grid grid-cols-1 sm:grid-cols-[280px_1fr]">
      {/* Sidebar */}
      <aside className="bg-[rgba(7,4,26,0.6)] border-r border-[var(--border-soft)] p-6 overflow-y-auto flex flex-col gap-0">
        <h1 className="font-display text-[22px] font-semibold tracking-tight mb-1.5">{biome.name}</h1>
        <div className="text-[11px] text-[var(--text-3)] font-mono tracking-[0.04em] flex items-center gap-2 mb-6">
          <span className="text-[#C4B5FD] bg-[rgba(124,58,237,0.18)] border border-[rgba(124,58,237,0.35)] px-2 py-px rounded-full text-[9px] font-semibold tracking-[0.08em] uppercase">
            {biome.lifecycle_state}
          </span>
          <span>{stardustPage?.total ?? biome.stardust_count} records</span>
        </div>

        {/* View toggle */}
        <div className="flex gap-1 p-1 bg-[rgba(255,255,255,0.04)] rounded-lg mb-6">
          {(['records', 'graph'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`flex-1 py-1.5 text-[11px] font-semibold tracking-[0.06em] uppercase rounded-md transition-all duration-150 ${
                view === v
                  ? 'bg-[rgba(124,58,237,0.3)] text-[#C4B5FD] border border-[rgba(124,58,237,0.4)]'
                  : 'text-[var(--text-3)] hover:text-[var(--text-2)]'
              }`}
            >
              {v}
            </button>
          ))}
        </div>

        <div className="h-px bg-[var(--border-soft)] mb-6" />

        <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-3">Filter by Region</h3>
        <div
          className="flex items-center gap-2.5 py-2 cursor-pointer transition-opacity duration-150 mb-1"
          style={{ opacity: activeRegion ? 0.5 : 1 }}
          onClick={() => setActiveRegion(null)}
        >
          <span className="w-2 h-2 rounded-full bg-[var(--text-3)]" />
          <span className="flex-1 text-[13px] text-[var(--text-1)]">All</span>
          <span className="font-mono text-[10px] text-[var(--text-3)]">{allRecords.length}</span>
        </div>
        {REGIONS.filter(r => allRecords.some((rec: any) => rec.region === r.key)).map((r) => {
          const count = allRecords.filter((rec: any) => rec.region === r.key).length;
          return (
            <div
              key={r.key}
              className="flex items-center gap-2.5 py-2 cursor-pointer transition-opacity duration-150"
              style={{ opacity: activeRegion && activeRegion !== r.key ? 0.35 : 1 }}
              onClick={() => setActiveRegion(activeRegion === r.key ? null : r.key)}
            >
              <span className="w-2 h-2 rounded-full" style={{ background: r.color, boxShadow: activeRegion === r.key ? `0 0 6px ${r.color}` : undefined }} />
              <span className="flex-1 text-[13px] text-[var(--text-1)]">{r.label}</span>
              <span className="font-mono text-[10px] text-[var(--text-3)]">{count}</span>
            </div>
          );
        })}

        <div className="h-px bg-[var(--border-soft)] my-6" />

        <div
          onClick={() => setSynthesisOpen(true)}
          className="flex items-center gap-2 px-3 py-2.5 bg-[var(--surface-3)] border border-[var(--border-soft)] rounded-lg text-xs text-[var(--text-2)] cursor-pointer hover:border-[var(--border)] hover:text-[var(--text-1)] transition-all duration-150"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          Synthesize this biome
        </div>
      </aside>

      {/* Main area */}
      <div className="relative overflow-hidden flex flex-col">
        {view === 'records' ? (
          <div className="flex-1 overflow-y-auto p-6">
            {records.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-24">
                <div className="w-10 h-10 rounded-full bg-[rgba(124,58,237,0.12)] flex items-center justify-center">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/></svg>
                </div>
                <p className="text-[13px] text-[var(--text-3)]">
                  {activeRegion ? `No ${activeRegion} records in this biome` : 'No records in this biome yet'}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3 max-w-3xl">
                {records.map((rec: any) => {
                  const color = REGION_COLORS[rec.region] || '#7C3AED';
                  const tags: string[] = rec.context_tags ?? [];
                  return (
                    <div
                      key={rec.id}
                      onClick={() => navigate(`/detail/stardust/${rec.id}`)}
                      className="group p-4 rounded-xl border border-[var(--border-soft)] bg-[rgba(255,255,255,0.025)] hover:bg-[rgba(255,255,255,0.045)] hover:border-[var(--border)] cursor-pointer transition-all duration-150"
                    >
                      <div className="flex items-center gap-2 mb-2.5">
                        <span
                          className="inline-flex items-center gap-1 px-2 py-px rounded-full text-[9px] font-semibold uppercase tracking-[0.08em] border"
                          style={{ color, background: `${color}20`, borderColor: `${color}40` }}
                        >
                          <span className="w-[5px] h-[5px] rounded-full bg-current" />
                          {rec.region}
                        </span>
                        <span className="ml-auto font-mono text-[10px] text-[var(--text-3)]">
                          {Math.round((rec.confidence ?? 0.5) * 100)}% conf
                        </span>
                        <div
                          className="w-12 h-1 rounded-full bg-[rgba(255,255,255,0.08)] overflow-hidden"
                          title={`Confidence: ${Math.round((rec.confidence ?? 0.5) * 100)}%`}
                        >
                          <div className="h-full rounded-full" style={{ width: `${(rec.confidence ?? 0.5) * 100}%`, background: color }} />
                        </div>
                      </div>

                      <p className="text-[13px] text-[var(--text-1)] leading-relaxed line-clamp-4">{rec.content}</p>

                      {tags.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap mt-2.5">
                          {tags.slice(0, 4).map((tag: string) => (
                            <span key={tag} className="text-[9px] font-mono text-[var(--text-3)] bg-[rgba(255,255,255,0.05)] border border-[var(--border-soft)] px-1.5 py-px rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <BiomeGraph biomeId={biomeId!} onNodeClick={(type, id) => navigate(`/detail/${type}/${id}`)} />
        )}
      </div>

      <SynthesisPanel open={synthesisOpen} onClose={() => setSynthesisOpen(false)} initialTopic={biome.name} />
    </div>
  );
}
