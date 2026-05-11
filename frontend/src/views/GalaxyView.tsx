import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useGalaxy } from '../api/galaxy';
import { apiClient } from '../api/client';
import { NavButton } from '../components/ui';
import GalaxyCanvas from '../components/galaxy/GalaxyCanvas';
import StrengthWidget from '../components/galaxy/StrengthWidget';
import NebulaDrawer from '../components/galaxy/NebulaDrawer';
import SunPanel from '../components/galaxy/SunPanel';
import CreatePlanetModal from '../components/galaxy/CreatePlanetModal';
import SearchModal from '../components/search/SearchModal';
import AskBar from '../components/search/AskBar';
import SynthesisPanel from '../components/search/SynthesisPanel';
import ContradictionPanel from '../components/galaxy/ContradictionPanel';
import AgentPanel from '../components/galaxy/AgentPanel';
import { InboxPanel } from '../components/inbox/InboxPanel';

export default function GalaxyView() {
  const { data: galaxy, isLoading } = useGalaxy();
  const [strengthExpanded, setStrengthExpanded] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sunOpen, setSunOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [agentOpen, setAgentOpen] = useState(false);
  const [contradictionOpen, setContradictionOpen] = useState(false);
  const [synthesisOpen, setSynthesisOpen] = useState(false);
  const [synthesisTopic, setSynthesisTopic] = useState('');
  const [askOpen, setAskOpen] = useState(false);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { data: inboxCount } = useQuery({
    queryKey: ['inbox-count', galaxy?.id],
    queryFn: () => apiClient.get(`/api/v1/routing/inbox?galaxy_id=${galaxy?.id}`).then(r => r.data?.length ?? 0),
    enabled: !!galaxy?.id,
    refetchInterval: 60000,
  });

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === 'Escape') {
        setSunOpen(false);
        setCreateOpen(false);
        setSearchOpen(false);
        setMoreOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Close overflow menu on outside click
  useEffect(() => {
    if (!moreOpen) return;
    const handler = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [moreOpen]);

  if (isLoading) return <div className="flex items-center justify-center h-screen text-[var(--text-3)]">Loading Galaxy...</div>;
  if (!galaxy) return <Navigate to="/onboarding" replace />;

  return (
    <div className="fixed inset-0">
      <GalaxyCanvas
        galaxy={galaxy}
        onPlanetClick={(id) => {
          const planet = galaxy.planets?.find((p: any) => p.id === id);
          if (planet?.planet_type === 'inbox') navigate('/inbox');
          else navigate(`/planet/${id}`);
        }}
        onSunClick={() => setSunOpen(true)}
      />

      {/* Top left: strength */}
      <div className="absolute top-7 left-8 z-[5] max-w-[280px] pointer-events-auto">
        <StrengthWidget expanded={strengthExpanded} onToggle={() => setStrengthExpanded(!strengthExpanded)} />
      </div>

      {/* Top right: actions */}
      <div className="absolute top-7 right-8 z-[5] flex gap-2.5 items-center pointer-events-auto">
        <NavButton onClick={() => setAskOpen(true)}>Ask</NavButton>
        <NavButton onClick={() => setSearchOpen(true)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="7"/><path d="m20 20-3-3"/></svg>
          Search
          <span className="font-mono text-[10px] text-[var(--text-3)] px-[5px] py-px border border-[var(--border-soft)] rounded bg-[rgba(0,0,0,0.3)]">⌘K</span>
        </NavButton>
        {(inboxCount ?? 0) > 0 && (
          <button onClick={() => setInboxOpen(true)}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-full bg-[rgba(245,158,11,0.15)] border border-[rgba(245,158,11,0.3)] text-[#F59E0B] text-xs font-medium cursor-pointer hover:bg-[rgba(245,158,11,0.25)] transition-colors">
            Inbox
            <span className="bg-[#F59E0B] text-[#07041A] rounded-full px-1.5 py-0.5 text-xs font-bold">{inboxCount}</span>
          </button>
        )}
        {/* Overflow menu for secondary actions */}
        <div ref={moreRef} className="relative">
          <NavButton
            onClick={() => setMoreOpen(!moreOpen)}
            aria-label="More actions"
            aria-expanded={moreOpen}
            className="w-8 !px-0 justify-center"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>
          </NavButton>
          {moreOpen && (
            <div className="absolute right-0 top-full mt-2 w-44 bg-[rgba(7,4,26,0.95)] backdrop-blur-sm border border-[var(--border)] rounded-xl py-1.5 shadow-[0_16px_32px_rgba(0,0,0,0.5)] animate-[fade-in_100ms_ease-out]">
              {[
                { label: 'Graph', action: () => navigate('/graph') },
                { label: 'Dashboard', action: () => navigate('/dashboard') },
                { label: 'Brain', action: () => setAgentOpen(!agentOpen) },
                { label: 'Conflicts', action: () => setContradictionOpen(!contradictionOpen) },
                { label: 'Settings', action: () => navigate('/settings') },
              ].map((item) => (
                <button
                  key={item.label}
                  onClick={() => { item.action(); setMoreOpen(false); }}
                  className="w-full text-left px-3.5 py-2 text-xs text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors duration-100"
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom left: planet legend */}
      <div className="absolute bottom-7 left-8 z-[5] pointer-events-auto">
        <div className="flex flex-col gap-1 px-3 py-2.5 rounded-xl bg-[rgba(7,4,26,0.75)] border border-[var(--border-soft)] backdrop-blur-sm">
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-3)] mb-0.5">Planets</span>
          {galaxy.planets?.map((p: { id: string; name: string; color?: string; stardust_count?: number }) => (
            <div
              key={p.id}
              className="inline-flex items-center gap-2 px-1.5 py-1 rounded-md text-xs text-[var(--text-1)] cursor-pointer hover:bg-[var(--surface-2)] transition-colors duration-100"
              onClick={() => navigate(`/planet/${p.id}`)}
            >
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color || '#7C3AED', boxShadow: `0 0 8px ${p.color || '#7C3AED'}` }} />
              {p.name}
              <span className="font-mono text-[11px] text-[var(--text-3)] ml-auto">{p.stardust_count?.toLocaleString()}</span>
            </div>
          ))}
          <div
            className="inline-flex items-center gap-2 px-1.5 py-1 rounded-md text-xs text-[var(--text-3)] cursor-pointer hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors duration-100 border-t border-[var(--border-soft)] mt-1 pt-1.5"
            onClick={() => setCreateOpen(true)}
          >
            <span className="w-2 h-2 rounded-full border border-dashed border-[var(--text-3)] flex-shrink-0" />
            Add planet
          </div>
        </div>
      </div>

      {/* Bottom center: nebula toggle */}
      <div className="absolute bottom-7 left-1/2 -translate-x-1/2 z-[5] pointer-events-auto">
        <NavButton onClick={() => setDrawerOpen(!drawerOpen)}>
          <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] shadow-[0_0_8px_#34D399] animate-[pulse-dot_2s_ease-in-out_infinite]" />
          Nebula stream
          <span className="text-[var(--text-3)]">↑</span>
        </NavButton>
      </div>

      {/* Nebula drawer */}
      <NebulaDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      {/* Sun panel */}
      <SunPanel open={sunOpen} onClose={() => setSunOpen(false)} />

      {/* Create planet modal */}
      <CreatePlanetModal open={createOpen} onClose={() => setCreateOpen(false)} />

      {/* Search modal */}
      {searchOpen && <SearchModal onClose={() => setSearchOpen(false)} onSynthesize={(t) => { setSynthesisTopic(t); setSynthesisOpen(true); }} />}

      {/* Agent panel */}
      <AgentPanel open={agentOpen} onClose={() => setAgentOpen(false)} />

      {/* Contradiction panel */}
      <ContradictionPanel open={contradictionOpen} onClose={() => setContradictionOpen(false)} />

      {/* Synthesis panel */}
      <SynthesisPanel open={synthesisOpen} onClose={() => setSynthesisOpen(false)} initialTopic={synthesisTopic} />

      {/* Ask bar */}
      {askOpen && <AskBar onClose={() => setAskOpen(false)} onSynthesize={(t) => { setSynthesisTopic(t); setSynthesisOpen(true); }} />}

      {/* Inbox panel */}
      {inboxOpen && galaxy && <InboxPanel galaxyId={galaxy.id} onClose={() => setInboxOpen(false)} />}
    </div>
  );
}
