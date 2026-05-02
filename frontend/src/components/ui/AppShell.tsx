import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import SearchModal from '../search/SearchModal';

interface Crumb { label: string; path?: string }

const ROUTE_LABELS: Record<string, string> = {
  planet: 'Planet',
  biome: 'Biome',
  detail: 'Detail',
  dashboard: 'Dashboard',
  sun: 'Sun',
  settings: 'Settings',
  graph: 'Knowledge Graph',
  onboarding: 'Onboarding',
};

function buildCrumbs(pathname: string): Crumb[] {
  const crumbs: Crumb[] = [{ label: 'Galaxy', path: '/' }];
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) return crumbs;

  const base = parts[0];
  const label = ROUTE_LABELS[base] || base;

  if (parts.length === 1) {
    crumbs.push({ label });
  } else if (base === 'planet') {
    crumbs.push({ label: 'Planet', path: `/planet/${parts[1]}` });
  } else if (base === 'biome') {
    crumbs.push({ label: 'Biome' });
  } else if (base === 'detail') {
    crumbs.push({ label: `${parts[1]?.[0]?.toUpperCase()}${parts[1]?.slice(1) || ''} Detail` });
  } else {
    crumbs.push({ label });
  }
  return crumbs;
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const crumbs = buildCrumbs(pathname);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="fixed inset-0 flex flex-col">
      <div className="space-backdrop" />
      <nav className="relative z-[5] flex items-center gap-3 px-6 py-3 border-b border-[var(--border-soft)] bg-[rgba(7,4,26,0.8)] backdrop-blur-sm">
        <button
          onClick={() => navigate('/')}
          className="text-[var(--text-2)] hover:text-[var(--text-1)] text-xs font-medium transition-colors"
        >
          ← Galaxy
        </button>
        <span className="text-[var(--border)] text-xs select-none">/</span>
        {crumbs.slice(1).map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="text-[var(--border)] text-xs select-none">/</span>}
            {c.path ? (
              <button onClick={() => navigate(c.path!)} className="text-[var(--text-3)] hover:text-[var(--text-1)] text-xs transition-colors">
                {c.label}
              </button>
            ) : (
              <span className="text-[var(--text-1)] text-xs font-medium">{c.label}</span>
            )}
          </React.Fragment>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setSearchOpen(true)}
            className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-[rgba(45,27,105,0.5)] border border-[var(--border-soft)] text-[var(--text-3)] text-[11px] hover:text-[var(--text-1)] hover:border-[var(--border)] transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="7"/><path d="m20 20-3-3"/></svg>
            Search
            <span className="font-mono text-[9px] text-[var(--text-3)] px-1 border border-[var(--border-soft)] rounded bg-[rgba(0,0,0,0.3)]">⌘K</span>
          </button>
        </div>
      </nav>
      <div className="relative z-[1] flex-1 overflow-auto">
        {children}
      </div>
      {searchOpen && <SearchModal onClose={() => setSearchOpen(false)} />}
    </div>
  );
}
