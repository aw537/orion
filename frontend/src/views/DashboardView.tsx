import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNebulaDashboard, useSessionsDaily, useAdminActiveAgents, useNebula } from '../api/dashboard';
import { useGalaxyStrength } from '../api/galaxy';
import { AreaChart, Area, LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const RANGES = [7, 30, 90] as const;
const TT = { contentStyle: { background: 'rgba(7,4,26,0.95)', border: '1px solid rgba(196,181,253,0.2)', borderRadius: 8, fontSize: 12 }, itemStyle: { color: '#C4B5FD' }, labelStyle: { color: '#9484C2' } };
const AGENT_COLORS = ['#7C3AED', '#34D399', '#F59E0B', '#EC4899', '#3B82F6', '#EF4444', '#8B5CF6', '#14B8A6'];
const ACTION_COLORS: Record<string, string> = { WRITE: '#7C3AED', READ: '#34D399', SESSION_START: '#3B82F6', SESSION_END: '#6B7280', AUDIT: '#F59E0B', ENTITY_EXTRACTED: '#EC4899', SUPERSESSION: '#EF4444', SESSION_SUMMARY: '#8B5CF6', INTEGRATION_COMPLETE: '#14B8A6', PLANET_ROUTED: '#10B981', INBOX_ROUTED: '#F59E0B', INBOX_RESOLVED: '#6D28D9' };

function fmtDate(d: string) { return d.slice(5); }
function timeAgo(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return 'just now';
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

export default function DashboardView() {
  const [days, setDays] = useState<number>(30);
  const navigate = useNavigate();
  const { data: dash, isLoading: dashLoading, isError: dashError, refetch } = useNebulaDashboard(days);
  const { data: strength } = useGalaxyStrength();
  const { data: agents } = useAdminActiveAgents();
  const { data: sessionsDaily } = useSessionsDaily(days);
  const { data: nebulaLog } = useNebula(20);

  if (dashLoading) return <div className="text-[var(--text-3)] p-8 font-body">Loading dashboard…</div>;
  if (dashError || !dash) return (
    <div className="p-8">
      <p className="text-[var(--danger)] font-body text-sm mb-3">Failed to load dashboard.</p>
      <button onClick={() => refetch()} className="px-3 py-1.5 rounded-full text-[11px] bg-[var(--surface-3)] text-[var(--text-3)] border border-[var(--border-soft)] hover:text-[var(--text-1)] hover:border-[var(--border)] transition-all duration-150">Retry</button>
    </div>
  );

  const s = dash.summary || {};
  const liveAgents = (agents || []).filter((a: any) => {
    if (!a.last_active) return false;
    return Date.now() - new Date(a.last_active).getTime() < 300_000;
  });
  const healthScore = s.avg_confidence || 0;
  const healthLabel = healthScore >= 0.8 ? 'healthy' : healthScore >= 0.6 ? 'moderate' : 'needs attention';
  const healthColor = healthScore >= 0.8 ? '#34D399' : healthScore >= 0.6 ? '#F59E0B' : '#DC2626';

  // Build stacked session chart data — pivot agents into columns
  const agentNames = new Set<string>();
  (sessionsDaily || []).forEach((d: any) => (d.agents || []).forEach((a: any) => agentNames.add(a.name)));
  const agentList = [...agentNames];
  const sessionChartData = (sessionsDaily || []).map((d: any) => {
    const row: any = { date: d.date };
    agentList.forEach(n => { row[n] = 0; });
    (d.agents || []).forEach((a: any) => { row[a.name] = a.sessions; });
    return row;
  });

  const events = nebulaLog?.events || [];

  return (
    <div className="min-h-screen p-8 max-w-6xl mx-auto relative">
      <div className="relative z-[1]">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <h1 className="font-display text-2xl font-semibold tracking-tight">Dashboard</h1>
          </div>
          <div className="flex gap-2">
            {RANGES.map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={`px-3 py-1.5 rounded-full text-[11px] font-mono border transition-all duration-150 ${days === d ? 'bg-[var(--violet-700)] text-white border-[var(--violet-700)]' : 'bg-[var(--surface-3)] text-[var(--text-3)] border-[var(--border-soft)] hover:text-[var(--text-1)] hover:border-[var(--border)]'}`}>
                {d}d
              </button>
            ))}
            <button onClick={() => refetch()} className="px-3 py-1.5 rounded-full text-[11px] bg-[var(--surface-3)] text-[var(--text-3)] border border-[var(--border-soft)] hover:text-[var(--text-1)] hover:border-[var(--border)] transition-all duration-150">↻</button>
          </div>
        </div>

        {/* Row 1: Headline cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {[
            { label: 'Galaxy Strength', value: strength?.score != null ? strength.score.toFixed(1) : '—', sub: strength?.trend && strength.trend !== 'first measurement' ? String(strength.trend) : '', color: 'var(--sun-core)' },
            { label: 'Knowledge Volume', value: s.total_stardust?.toLocaleString() ?? '—', sub: `+${s.added_this_week || 0}/wk`, color: 'var(--violet-300)' },
            { label: 'Agent Activity', value: `${(agents || []).length} today`, sub: `${liveAgents.length} live`, color: '#34D399' },
            { label: 'Health Score', value: healthScore.toFixed(2), sub: healthLabel, color: healthColor },
          ].map((c, i) => (
            <div key={i} className="p-4 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
              <p className="text-2xl font-semibold font-mono" style={{ color: c.color }}>{c.value}</p>
              <p className="text-[10px] text-[var(--text-3)] uppercase tracking-[0.08em] mt-1">{c.label}</p>
              {c.sub && <p className="text-[11px] font-mono mt-0.5" style={{ color: c.color, opacity: 0.7 }}>{c.sub}</p>}
            </div>
          ))}
        </div>

        {/* Row 2: Time-series charts */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
          {/* Knowledge Growth */}
          <div className="p-5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
            <h2 className="font-display text-sm font-medium mb-4">Knowledge Growth</h2>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={dash.growth_over_time || []}>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9484C2' }} tickFormatter={fmtDate} />
                <YAxis tick={{ fontSize: 10, fill: '#9484C2' }} />
                <Tooltip {...TT} />
                <Area type="monotone" dataKey="cumulative" stroke="#7C3AED" fill="#7C3AED" fillOpacity={0.2} name="Cumulative" />
                <Area type="monotone" dataKey="records_added" stroke="#34D399" fill="#34D399" fillOpacity={0.15} name="Daily" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Agent Sessions */}
          <div className="p-5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
            <h2 className="font-display text-sm font-medium mb-4">Agent Sessions</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sessionChartData}>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9484C2' }} tickFormatter={fmtDate} />
                <YAxis tick={{ fontSize: 10, fill: '#9484C2' }} allowDecimals={false} />
                <Tooltip {...TT} />
                {agentList.map((name, i) => (
                  <Bar key={name} dataKey={name} stackId="sessions" fill={AGENT_COLORS[i % AGENT_COLORS.length]} radius={i === agentList.length - 1 ? [4, 4, 0, 0] : undefined} />
                ))}
                {agentList.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: '#9484C2' }} />}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Row 3: Health panels */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
          {/* Planet Health */}
          <div className="p-5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
            <h2 className="font-display text-sm font-medium mb-4">Planet Health</h2>
            <div className="space-y-2">
              {(dash.activity_by_biome || []).reduce((planets: any[], b: any) => {
                if (!planets.find((p: any) => p.planet_name === b.planet_name)) {
                  planets.push({ planet_name: b.planet_name, write_count: b.write_count, read_count: b.read_count, stardust_count: b.stardust_count });
                } else {
                  const p = planets.find((p: any) => p.planet_name === b.planet_name);
                  p.write_count += b.write_count;
                  p.read_count += b.read_count;
                  p.stardust_count += b.stardust_count;
                }
                return planets;
              }, []).map((p: any) => {
                const maxCount = Math.max(...(dash.activity_by_biome || []).map((b: any) => b.stardust_count || 1));
                const pct = Math.max(10, (p.stardust_count / maxCount) * 100);
                const color = p.write_count > 0 ? '#34D399' : '#F59E0B';
                return (
                  <div key={p.planet_name} className="flex items-center gap-3">
                    <span className="text-xs text-[var(--text-1)] w-28 truncate">{p.planet_name}</span>
                    <div className="flex-1 h-5 bg-[var(--surface-3)] rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, background: color, opacity: 0.7 }} />
                    </div>
                    <span className="text-[11px] font-mono text-[var(--text-3)] w-16 text-right">{p.stardust_count}</span>
                  </div>
                );
              })}
              {(!dash.activity_by_biome || dash.activity_by_biome.length === 0) && <p className="text-[var(--text-3)] text-xs py-2">No planet activity yet. Start a session to write knowledge.</p>}
            </div>
          </div>

          {/* Contradiction Tracker */}
          <div className="p-5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
            <h2 className="font-display text-sm font-medium mb-4">Contradiction Tracker</h2>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={dash.contradiction_trend || []}>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9484C2' }} tickFormatter={fmtDate} />
                <YAxis tick={{ fontSize: 10, fill: '#9484C2' }} allowDecimals={false} />
                <Tooltip {...TT} />
                <Line type="monotone" dataKey="detected" stroke="#F59E0B" strokeWidth={1.5} dot={false} name="Detected" />
                <Line type="monotone" dataKey="resolved" stroke="#34D399" strokeWidth={1.5} dot={false} name="Resolved" />
              </LineChart>
            </ResponsiveContainer>
            {(s.unresolved_contradictions || 0) > 0 && (
              <p className="text-[11px] mt-2 text-[var(--warning)]">{s.unresolved_contradictions} unresolved</p>
            )}
          </div>
        </div>

        {/* Row 4: Intelligence panels */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
          {/* Top Entities */}
          <div className="p-5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
            <h2 className="font-display text-sm font-medium mb-4">Top Entities</h2>
            <div className="space-y-1">
              {(dash.top_entities || []).slice(0, 10).map((e: any) => (
                <div key={e.id} onClick={() => navigate('/graph')}
                  className="flex items-center gap-3 text-xs p-2 rounded-lg cursor-pointer hover:bg-[var(--surface-2)] transition-colors duration-150">
                  <span className="w-2.5 h-2.5 rotate-45 rounded-[1px]" style={{ background: e.tier >= 3 ? '#A78BFA' : e.tier >= 2 ? '#7C3AED' : '#4B5563' }} />
                  <span className="font-medium text-[var(--text-1)] w-28 truncate">{e.name}</span>
                  <span className="text-[var(--text-3)] font-mono text-[11px] w-14">{e.entity_type}</span>
                  <span className="text-[var(--text-3)] font-mono text-[11px]">{e.linked_stardust} records · {e.biomes_spanning} biomes</span>
                </div>
              ))}
              {(!dash.top_entities || dash.top_entities.length === 0) && <p className="text-[var(--text-3)] text-xs py-2">No entities yet. Entities are extracted automatically from your knowledge.</p>}
            </div>
          </div>

          {/* Knowledge Gaps */}
          <div className="p-5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
            <h2 className="font-display text-sm font-medium mb-4">Knowledge Gaps</h2>
            <div className="space-y-1">
              {(dash.knowledge_gaps || []).map((g: any) => (
                <div key={g.biome_id} onClick={() => navigate(`/biome/${g.biome_id}`)}
                  className="flex items-center justify-between p-2.5 rounded-lg cursor-pointer hover:bg-[var(--surface-2)] transition-colors duration-150">
                  <span className="text-xs text-[var(--text-1)]">{g.read_write_ratio > 5 ? '' : ''}{g.biome_name}</span>
                  <span className="text-[11px] font-mono" style={{ color: g.read_write_ratio > 10 ? 'var(--danger)' : g.read_write_ratio > 5 ? 'var(--warning)' : 'var(--text-3)' }}>{g.read_write_ratio}× reads</span>
                </div>
              ))}
              {(!dash.knowledge_gaps || dash.knowledge_gaps.length === 0) && <p className="text-[var(--text-3)] text-xs py-2">No knowledge gaps detected.</p>}
            </div>
          </div>
        </div>

        {/* Row 5: Activity Stream */}
        <div className="p-5 rounded-xl bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)]">
          <h2 className="font-display text-sm font-medium mb-4">Recent Activity</h2>
          <div className="space-y-1">
            {events.slice(0, 20).map((e: any) => (
              <div key={e.event_id}
                onClick={() => e.record_id ? navigate(`/detail/stardust/${e.record_id}`) : undefined}
                className={`flex items-center gap-3 text-xs p-2 rounded-lg transition-colors duration-150 ${e.record_id ? 'cursor-pointer hover:bg-[var(--surface-2)]' : ''}`}>
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: ACTION_COLORS[e.action_type] || '#6B7280' }} />
                <span className="text-[var(--text-3)] font-mono text-[11px] w-14 flex-shrink-0">{e.action_type.replace(/_/g, ' ').toLowerCase()}</span>
                <span className="text-[var(--text-2)] truncate flex-1">{e.initiated_by || '—'}</span>
                <span className="text-[var(--text-3)] font-mono text-[11px] flex-shrink-0" title={e.timestamp || ''}>{e.timestamp ? timeAgo(e.timestamp) : ''}</span>
              </div>
            ))}
            {events.length === 0 && <p className="text-[var(--text-3)] text-xs py-2">No recent activity. Connect an agent and start a session.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
