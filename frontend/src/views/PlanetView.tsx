import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePlanet } from '../api/planets';
import { theme } from '../theme';

interface Biome {
  id: string;
  name: string;
  lifecycle_state: string;
  stardust_count: number;
}

const LIFECYCLE_STYLES: Record<string, { color: string; cls: string }> = {
  ACTIVE: { color: '#7C3AED', cls: 'text-[#C4B5FD] bg-[rgba(124,58,237,0.18)] border-[rgba(124,58,237,0.35)]' },
  MATURE: { color: '#4F46E5', cls: 'text-[#818CF8] bg-[rgba(79,70,229,0.18)] border-[rgba(79,70,229,0.35)]' },
  DORMANT: { color: '#4B5563', cls: 'text-[#9CA3AF] bg-[rgba(75,85,99,0.20)] border-[rgba(75,85,99,0.40)]' },
  SEED: { color: '#22D3EE', cls: 'text-[#67E8F9] bg-[rgba(34,211,238,0.12)] border-[rgba(34,211,238,0.30)]' },
  ARCHIVED: { color: '#374151', cls: 'text-[#6B7280] bg-[rgba(55,65,81,0.20)] border-[rgba(55,65,81,0.40)]' },
};

// Biome positions on the planet SVG (relative to 600x600 viewBox)
const BIOME_POSITIONS = [
  { x: 220, y: 230, r: 44, glowR: 58 },
  { x: 390, y: 320, r: 32, glowR: 42 },
  { x: 280, y: 410, r: 24, glowR: 34 },
  { x: 390, y: 200, r: 14, glowR: 22 },
];

export default function PlanetView() {
  const { planetId } = useParams<{ planetId: string }>();
  const { data: planet, isLoading } = usePlanet(planetId!);
  const navigate = useNavigate();
  const [hoverBiome, setHoverBiome] = useState<string | null>(null);

  if (isLoading || !planet) return <div className="flex items-center justify-center h-screen text-[var(--text-3)]">Loading Planet...</div>;

  const biomes = planet.biomes || [];
  const planetColor = planet.color || '#7C3AED';

  return (
    <div className="h-full relative">
      {/* Blurred galaxy backdrop */}
      <div className="absolute inset-0 pointer-events-none opacity-70" style={{ filter: 'blur(12px) brightness(0.55) saturate(0.85)', transform: 'scale(1.06)' }}>
        <div className="w-full h-full" style={{ background: `radial-gradient(circle at 50% 50%, rgba(245,158,11,0.15), transparent 40%), var(--bg)` }} />
      </div>
      <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse 80% 70% at 50% 50%, transparent 0%, rgba(7,4,26,0.65) 70%, rgba(7,4,26,0.85) 100%)' }} />

      {/* Header */}
      <div className="absolute top-0 left-0 right-0 sm:right-[360px] flex items-center justify-between px-8 py-6 z-[5]">
        <div className="flex items-center gap-3.5">
          <div className="flex items-center gap-3.5">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: planetColor, boxShadow: `0 0 12px ${planetColor}` }} />
            <h1 className="font-display text-lg font-medium">{planet.name}</h1>
            <span className="font-mono text-[11px] text-[var(--text-3)]">{planet.stardust_count} stardust · {biomes.length} biomes</span>
          </div>
        </div>
      </div>

      {/* Planet SVG */}
      <div className="absolute left-0 top-0 bottom-0 right-0 sm:right-[360px] flex items-center justify-center animate-[rise_600ms_ease-expo]">
        <svg className="w-[70vh] h-[70vh] max-w-[720px] max-h-[720px]" viewBox="0 0 600 600" style={{ filter: `drop-shadow(0 0 80px ${planetColor}40)` }}>
          <defs>
            <radialGradient id="planet-body" cx="40%" cy="35%" r="70%">
              <stop offset="0%" stopColor={planetColor} stopOpacity="0.7" />
              <stop offset="40%" stopColor={planetColor} />
              <stop offset="80%" stopColor={theme.colors.nebula} />
              <stop offset="100%" stopColor={theme.colors.nebula} />
            </radialGradient>
            <radialGradient id="atmo" cx="50%" cy="50%" r="55%">
              <stop offset="80%" stopColor={planetColor} stopOpacity="0" />
              <stop offset="92%" stopColor={planetColor} stopOpacity="0.25" />
              <stop offset="100%" stopColor={planetColor} stopOpacity="0" />
            </radialGradient>
            <radialGradient id="spec" cx="35%" cy="28%" r="35%">
              <stop offset="0%" stopColor="rgba(255,255,255,0.35)" />
              <stop offset="100%" stopColor="rgba(255,255,255,0)" />
            </radialGradient>
            <clipPath id="planet-clip"><circle cx="300" cy="300" r="220" /></clipPath>
            <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <circle cx="300" cy="300" r="260" fill="url(#atmo)" />
          <circle cx="300" cy="300" r="220" fill="url(#planet-body)" />
          <g clipPath="url(#planet-clip)">
            <ellipse cx="360" cy="240" rx="140" ry="80" fill="rgba(167,139,250,0.18)" />
            <ellipse cx="200" cy="380" rx="160" ry="100" fill="rgba(45,27,105,0.45)" />
            <ellipse cx="300" cy="300" rx="220" ry="8" fill="rgba(255,255,255,0.025)" />
          </g>
          <circle cx="300" cy="300" r="220" fill="url(#spec)" />
          <ellipse cx="380" cy="300" rx="80" ry="220" fill="rgba(7,4,26,0.18)" clipPath="url(#planet-clip)" />

          {/* Biome zones */}
          {biomes.slice(0, 4).map((b: Biome, i: number) => {
            const pos = BIOME_POSITIONS[i] || BIOME_POSITIONS[0];
            const lc = LIFECYCLE_STYLES[b.lifecycle_state] || LIFECYCLE_STYLES.ACTIVE;
            return (
              <g
                key={b.id}
                className="cursor-pointer transition-transform duration-200 ease-expo origin-center"
                style={{ transformBox: 'fill-box' as any }}
                transform={`translate(${pos.x} ${pos.y})`}
                onClick={() => navigate(`/biome/${b.id}`)}
                onMouseEnter={() => setHoverBiome(b.id)}
                onMouseLeave={() => setHoverBiome(null)}
              >
                <circle r={pos.glowR} fill={`${lc.color}40`} filter="url(#glow)" />
                <circle r={pos.r} fill={lc.color} stroke="rgba(255,255,255,0.18)" strokeWidth="1" />
                <circle r={pos.r * 0.3} cx={-pos.r * 0.25} cy={-pos.r * 0.3} fill="rgba(255,255,255,0.18)" />
                <text x="0" y={pos.r + 20} textAnchor="middle" className="font-body text-xs font-medium" fill="var(--text-1)">{b.name}</text>
                <text x="0" y={pos.r + 34} textAnchor="middle" className="font-mono text-[9px] uppercase tracking-[0.08em]" fill="var(--text-3)">{b.lifecycle_state} · {b.stardust_count}</text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Right panel */}
      <aside className="absolute top-0 right-0 bottom-0 w-full sm:w-[360px] bg-[rgba(7,4,26,0.88)] backdrop-blur-[18px] border-l border-[var(--border-soft)] z-[4] flex flex-col animate-[panel-in_360ms_ease-expo]">
        <div className="px-6 pt-5 pb-4 border-b border-[var(--border-soft)]">
          <div className="text-[11px] text-[var(--text-3)] uppercase tracking-[0.08em] mb-2">Galaxy / {planet.name}</div>
          <h2 className="font-display text-[22px] font-semibold tracking-tight mb-2.5">{planet.name}</h2>
          <div className="flex gap-2 flex-wrap">
            <span className={`inline-flex items-center gap-1.5 h-[22px] px-2.5 rounded-full text-[10px] font-semibold tracking-[0.08em] uppercase border ${LIFECYCLE_STYLES[planet.health_status || 'ACTIVE']?.cls || LIFECYCLE_STYLES.ACTIVE.cls}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current" />
              {planet.health_status || 'Active'}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Stats */}
          <section className="px-6 py-4 border-b border-[var(--border-soft)]">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-3">Stats</h3>
            {[
              ['Total stardust', planet.stardust_count],
              ['Active biomes', biomes.length],
            ].map(([k, v]) => (
              <div key={k as string} className="flex items-baseline justify-between py-1.5 text-xs">
                <span className="text-[var(--text-3)]">{k}</span>
                <span className="font-mono text-[var(--text-1)]">{v}</span>
              </div>
            ))}
          </section>

          {/* Biomes */}
          <section className="px-6 py-4 border-b border-[var(--border-soft)]">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-3 flex items-center justify-between">
              Biomes <span className="font-mono font-normal text-[10px]">{biomes.length}</span>
            </h3>
            {biomes.map((b: Biome) => {
              const lc = LIFECYCLE_STYLES[b.lifecycle_state] || LIFECYCLE_STYLES.ACTIVE;
              return (
                <div
                  key={b.id}
                  className="grid grid-cols-[12px_1fr_auto] gap-3 items-center py-2.5 cursor-pointer hover:opacity-80 transition-opacity duration-150"
                  onClick={() => navigate(`/biome/${b.id}`)}
                >
                  <span className="w-2 h-2 rounded-full" style={{ background: lc.color, boxShadow: b.lifecycle_state === 'ACTIVE' || b.lifecycle_state === 'SEED' ? `0 0 8px ${lc.color}` : undefined }} />
                  <div>
                    <div className="text-[13px] text-[var(--text-1)] font-medium">{b.name}</div>
                    <div className="text-[11px] text-[var(--text-3)] mt-0.5">{b.lifecycle_state} · {b.stardust_count} stardust</div>
                  </div>
                  <div className="font-mono text-xs text-[var(--text-2)] text-right">{b.stardust_count}</div>
                </div>
              );
            })}
          </section>
        </div>
      </aside>
    </div>
  );
}
