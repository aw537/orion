import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import { theme, hexA } from '../../theme';
import { useNebulaStore } from '../../store/nebulaStore';
import { useNebulaStream } from '../../hooks/useNebulaStream';
import { apiClient } from '../../api/client';

interface Planet {
  id: string;
  name: string;
  stardust_count: number;
  color?: string;
  planet_type?: string;
  active_biomes?: string[];
  health_status?: string;
}
interface GalaxyData {
  id: string;
  name: string;
  strength_score: number;
  planets: Planet[];
}
interface Props {
  galaxy: GalaxyData;
  onPlanetClick: (id: string) => void;
  onSunClick: () => void;
}

interface Star { x: number; y: number; r: number; baseO: number; phase: number; period: number }
interface PlanetState {
  id: string; name: string; angle: number; speed: number; orbitR: number; r: number;
  color: string; dust: number; biomes: number; _x: number; _y: number; planetType?: string;
}
interface Bridge { a: string; b: string }
interface Pulse { planet: PlanetState; t0: number; dur: number; color: string }

const DPR = Math.min(window.devicePixelRatio || 1, 2);

export default React.memo(function GalaxyCanvas({ galaxy, onPlanetClick, onSunClick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef<{
    stars: Star[]; planets: PlanetState[]; bridges: Bridge[]; pulses: Pulse[];
    zoom: number; hoverPlanet: PlanetState | null; hoverSun: boolean;
    mouseX: number; mouseY: number; W: number; H: number;
    brainHealthLow: boolean; focusedIdx: number | null;
  }>({
    stars: [], planets: [], bridges: [], pulses: [],
    zoom: 1, hoverPlanet: null, hoverSun: false, mouseX: -1, mouseY: -1,
    W: window.innerWidth, H: window.innerHeight, brainHealthLow: false, focusedIdx: null,
  });
  const [hoverInfo, setHoverInfo] = useState<{ planet: PlanetState; cssX: number; cssY: number } | null>(null);
  const [sunHover, setSunHover] = useState(false);
  const [zoom, setZoomState] = useState(1);
  // Keyboard focus: -1 = sun, 0..n-1 = planet index, null = no focus
  const [focusedIdx, setFocusedIdx] = useState<number | null>(null);
  const events = useNebulaStore((s) => s.events);
  useNebulaStream();

  // Check brain health for amber Sun tint
  useEffect(() => {
    stateRef.current.focusedIdx = focusedIdx;
  }, [focusedIdx]);

  useEffect(() => {
    apiClient.get<{ agent_name: string }[]>('/api/v1/agents').then(async (agents) => {
      for (const a of agents) {
        try {
          const h = await apiClient.get<{ overall_health: number }>(`/api/v1/agents/${a.agent_name}/health`);
          if (h.overall_health < 0.8) { stateRef.current.brainHealthLow = true; return; }
        } catch (err) {
          console.error('Agent health check failed:', err);
        }
      }
      stateRef.current.brainHealthLow = false;
    }).catch((err) => { console.error('Agents fetch failed:', err); });
  }, []);

  // Init stars + planets
  useEffect(() => {
    const s = stateRef.current;
    s.stars = Array.from({ length: theme.animation.starCount }, () => ({
      x: Math.random(), y: Math.random(), r: 0.4 + Math.random() * 1.2,
      baseO: 0.1 + Math.random() * 0.6, phase: Math.random() * Math.PI * 2,
      period: 3000 + Math.random() * 5000,
    }));
    const colors = theme.colors.planets;
    const n = galaxy.planets.length;
    // Distribute orbits evenly within the visible viewport so all planets fit at zoom=1
    const viewportMin = Math.min(s.W || window.innerWidth, s.H || window.innerHeight) / 2;
    const minOrbit = Math.round(viewportMin * 0.30);
    const maxOrbit = Math.round(viewportMin * 0.82);
    s.planets = (galaxy.planets || []).map((p, i) => ({
      id: p.id, name: p.name,
      angle: (Math.PI * 2 * i) / Math.max(n, 1),
      speed: theme.animation.orbitSpeed * (1 - i * 0.08),
      orbitR: n <= 1 ? minOrbit : Math.round(minOrbit + ((maxOrbit - minOrbit) * i) / (n - 1)),
      r: Math.max(16, Math.min(30, 14 + Math.sqrt(p.stardust_count) * 0.5)),
      color: colors[p.name.toLowerCase()] || p.color || theme.colors.planetDefault,
      dust: p.stardust_count, biomes: p.active_biomes?.length || 0,
      _x: 0, _y: 0, planetType: p.planet_type,
    }));
    s.bridges = [];
    if (s.planets.length >= 2) s.bridges.push({ a: s.planets[0].id, b: s.planets[1].id });
    if (s.planets.length >= 3) s.bridges.push({ a: s.planets[0].id, b: s.planets[2].id });
  }, [galaxy]);

  // SSE-driven pulses
  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[0];
    const target = stateRef.current.planets.find((p) => p.id === latest.planet_id);
    if (target) {
      stateRef.current.pulses.push({ planet: target, t0: performance.now(), dur: 800, color: target.color });
    }
  }, [events.length]);

  // Scheduled auto-pulses (sun → random planet), matching design's schedulePulse()
  useEffect(() => {
    let tid: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const delay = 800 + Math.random() * 2200;
      tid = setTimeout(() => {
        const s = stateRef.current;
        if (s.planets.length > 0) {
          const target = s.planets[Math.floor(Math.random() * s.planets.length)];
          s.pulses.push({ planet: target, t0: performance.now(), dur: 700 + Math.random() * 400, color: target.color });
        }
        schedule();
      }, delay);
    };
    schedule();
    return () => clearTimeout(tid);
  }, []);

  // Canvas resize via ResizeObserver
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const { width, height } = e.contentRect;
        canvas.width = width * DPR;
        canvas.height = height * DPR;
        stateRef.current.W = width;
        stateRef.current.H = height;
      }
    });
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    let animId: number;

    const draw = (now: number) => {
      const s = stateRef.current;
      const { W, H } = s;
      const z = s.zoom;
      const CX = W / 2, CY = H / 2;

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Stars drawn in screen space so they fill the full canvas at any zoom level
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      for (const star of s.stars) {
        const tw = 0.5 + 0.5 * Math.sin(now / star.period * Math.PI * 2 + star.phase);
        const o = star.baseO * (0.3 + 0.7 * tw);
        ctx.fillStyle = `rgba(243, 240, 255, ${o})`;
        ctx.beginPath();
        ctx.arc(star.x * W, star.y * H, star.r, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.setTransform(DPR * z, 0, 0, DPR * z, DPR * CX * (1 - z), DPR * CY * (1 - z));

      // Orbit rings
      ctx.save();
      ctx.setLineDash([3, 6]);
      ctx.strokeStyle = 'rgba(196, 181, 253, 0.12)';
      ctx.lineWidth = 1;
      for (const p of s.planets) {
        ctx.beginPath();
        ctx.arc(CX, CY, p.orbitR, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();

      // Gravity bridges
      for (const b of s.bridges) {
        const A = s.planets.find(p => p.id === b.a);
        const B = s.planets.find(p => p.id === b.b);
        if (!A || !B) continue;
        const mx = (A._x + B._x) / 2, my = (A._y + B._y) / 2;
        const dx = mx - CX, dy = my - CY;
        const len = Math.hypot(dx, dy) || 1;
        const cpx = mx + (dx / len) * 80, cpy = my + (dy / len) * 80;

        ctx.save();
        ctx.setLineDash([8, 6]);
        ctx.lineDashOffset = -now / 60;
        ctx.strokeStyle = 'rgba(14, 165, 233, 0.28)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(A._x, A._y);
        ctx.quadraticCurveTo(cpx, cpy, B._x, B._y);
        ctx.stroke();
        ctx.restore();

        // Particle along bridge
        const pt = ((now / 3200) % 1);
        const ix = (1 - pt) ** 2 * A._x + 2 * (1 - pt) * pt * cpx + pt ** 2 * B._x;
        const iy = (1 - pt) ** 2 * A._y + 2 * (1 - pt) * pt * cpy + pt ** 2 * B._y;
        ctx.fillStyle = 'rgba(56, 189, 248, 0.9)';
        ctx.beginPath(); ctx.arc(ix, iy, 2, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = 'rgba(56, 189, 248, 0.25)';
        ctx.beginPath(); ctx.arc(ix, iy, 6, 0, Math.PI * 2); ctx.fill();
      }

      // Sun
      const sunPulse = 1 + 0.04 * Math.sin(now / 2000);
      const sunR = 32 * sunPulse * (s.hoverSun ? 1.06 : 1);
      const g1 = ctx.createRadialGradient(CX, CY, 0, CX, CY, 140);
      // Amber tint when any agent brain health < 0.8
      const amberTint = s.brainHealthLow;
      g1.addColorStop(0, amberTint ? 'rgba(245, 158, 11, 0.28)' : 'rgba(245, 158, 11, 0.18)');
      g1.addColorStop(0.4, amberTint ? 'rgba(245, 158, 11, 0.14)' : 'rgba(245, 158, 11, 0.08)');
      g1.addColorStop(1, 'rgba(245, 158, 11, 0)');
      ctx.fillStyle = g1;
      ctx.beginPath(); ctx.arc(CX, CY, 140, 0, Math.PI * 2); ctx.fill();

      const g2 = ctx.createRadialGradient(CX, CY, 0, CX, CY, 90);
      g2.addColorStop(0, 'rgba(252, 211, 77, 0.3)');
      g2.addColorStop(0.6, 'rgba(252, 211, 77, 0.1)');
      g2.addColorStop(1, 'rgba(252, 211, 77, 0)');
      ctx.fillStyle = g2;
      ctx.beginPath(); ctx.arc(CX, CY, 90, 0, Math.PI * 2); ctx.fill();

      ctx.fillStyle = theme.colors.sun;
      ctx.beginPath(); ctx.arc(CX, CY, sunR, 0, Math.PI * 2); ctx.fill();

      const g3 = ctx.createRadialGradient(CX - sunR * 0.25, CY - sunR * 0.3, 0, CX, CY, sunR);
      g3.addColorStop(0, 'rgba(254, 243, 199, 0.9)');
      g3.addColorStop(0.5, 'rgba(252, 211, 77, 0.6)');
      g3.addColorStop(1, 'rgba(245, 158, 11, 0)');
      ctx.fillStyle = g3;
      ctx.beginPath(); ctx.arc(CX, CY, sunR * 0.85, 0, Math.PI * 2); ctx.fill();

      // Sun hover detection
      const sdx = s.mouseX - CX, sdy = s.mouseY - CY;
      const newSunHover = (sdx * sdx + sdy * sdy) < (sunR + 6) ** 2;
      if (newSunHover !== s.hoverSun) {
        s.hoverSun = newSunHover;
        setSunHover(newSunHover);
      }

      // Keyboard focus ring on sun
      if (s.focusedIdx === -1) {
        ctx.save();
        ctx.strokeStyle = 'rgba(196, 181, 253, 0.8)';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.arc(CX, CY, sunR + 8, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      // Update planet positions
      for (const p of s.planets) {
        p.angle += p.speed;
        p._x = CX + Math.cos(p.angle) * p.orbitR;
        p._y = CY + Math.sin(p.angle) * p.orbitR;
      }

      // Planet hover detection
      let newHover: PlanetState | null = null;
      for (const p of s.planets) {
        const dx = s.mouseX - p._x, dy = s.mouseY - p._y;
        if (dx * dx + dy * dy < (p.r + 6) ** 2) newHover = p;
      }

      // Draw atmospheres
      for (const p of s.planets) {
        const isH = newHover?.id === p.id;
        const atmoR = p.r * (isH ? 3.2 : 2.5);
        const atmo = ctx.createRadialGradient(p._x, p._y, 0, p._x, p._y, atmoR);
        atmo.addColorStop(0, hexA(p.color, isH ? 0.5 : 0.32));
        atmo.addColorStop(0.5, hexA(p.color, isH ? 0.18 : 0.1));
        atmo.addColorStop(1, hexA(p.color, 0));
        ctx.fillStyle = atmo;
        ctx.beginPath(); ctx.arc(p._x, p._y, atmoR, 0, Math.PI * 2); ctx.fill();
      }

      // Draw planet bodies + labels
      for (const p of s.planets) {
        const isH = newHover?.id === p.id;
        const r = p.r * (isH ? 1.08 : 1);

        if (p.planetType === 'inbox') {
          // Inbox planet: dashed ring + diamond shape
          ctx.save();
          ctx.strokeStyle = p.color;
          ctx.lineWidth = 2;
          ctx.setLineDash([4, 4]);
          ctx.lineDashOffset = -now / 200;
          ctx.beginPath(); ctx.arc(p._x, p._y, r + 4, 0, Math.PI * 2); ctx.stroke();
          ctx.restore();
          // Inner filled diamond
          ctx.fillStyle = p.color;
          ctx.beginPath();
          ctx.moveTo(p._x, p._y - r * 0.8);
          ctx.lineTo(p._x + r * 0.6, p._y);
          ctx.lineTo(p._x, p._y + r * 0.8);
          ctx.lineTo(p._x - r * 0.6, p._y);
          ctx.closePath();
          ctx.fill();
        } else {
          ctx.fillStyle = p.color;
          ctx.beginPath(); ctx.arc(p._x, p._y, r, 0, Math.PI * 2); ctx.fill();
          ctx.save();
          ctx.translate(p._x - r * 0.3, p._y - r * 0.35);
          ctx.scale(1, 0.55);
          const hl = ctx.createRadialGradient(0, 0, 0, 0, 0, r * 0.65);
          hl.addColorStop(0, 'rgba(255, 255, 255, 0.32)');
          hl.addColorStop(1, 'rgba(255, 255, 255, 0)');
          ctx.fillStyle = hl;
          ctx.beginPath(); ctx.arc(0, 0, r * 0.65, 0, Math.PI * 2); ctx.fill();
          ctx.restore();
        }

        ctx.fillStyle = '#C4B5FD';
        ctx.font = '500 12px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(p.name, p._x, p._y + r + 22);
        ctx.fillStyle = '#9484C2';
        ctx.font = '500 11px "JetBrains Mono", monospace';
        ctx.fillText(p.planetType === 'inbox' ? 'drop files' : `${p.dust.toLocaleString()} · ${p.biomes} biomes`, p._x, p._y + r + 38);

        // Keyboard focus ring
        if (s.focusedIdx !== null && s.focusedIdx >= 0 && s.planets[s.focusedIdx]?.id === p.id) {
          ctx.save();
          ctx.strokeStyle = 'rgba(196, 181, 253, 0.8)';
          ctx.lineWidth = 2;
          ctx.setLineDash([6, 4]);
          ctx.beginPath();
          ctx.arc(p._x, p._y, r + 8, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        }
      }

      // Pulses
      for (let i = s.pulses.length - 1; i >= 0; i--) {
        const pl = s.pulses[i];
        const t = (now - pl.t0) / pl.dur;
        if (t >= 1) { s.pulses.splice(i, 1); continue; }
        const e = 1 - (1 - t) ** 2.2;
        const px = CX + (pl.planet._x - CX) * e;
        const py = CY + (pl.planet._y - CY) * e;
        const fade = t < 0.75 ? 1 : (1 - (t - 0.75) / 0.25);
        ctx.fillStyle = hexA(pl.color, fade);
        ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fill();
        const gl = ctx.createRadialGradient(px, py, 0, px, py, 14);
        gl.addColorStop(0, hexA(pl.color, 0.6 * fade));
        gl.addColorStop(1, hexA(pl.color, 0));
        ctx.fillStyle = gl;
        ctx.beginPath(); ctx.arc(px, py, 14, 0, Math.PI * 2); ctx.fill();
      }

      // Update hover info — convert world coords to CSS screen coords
      if (newHover !== s.hoverPlanet) {
        s.hoverPlanet = newHover;
        if (newHover) {
          setHoverInfo({
            planet: newHover,
            cssX: CX + (newHover._x - CX) * z,
            cssY: CY + (newHover._y - CY) * z,
          });
        } else {
          setHoverInfo(null);
        }
      }

      animId = requestAnimationFrame(draw);
    };
    animId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animId);
  }, []);

  // Keyboard zoom + planet navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't capture when typing in inputs
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const s = stateRef.current;
      const count = s.planets.length; // -1=sun, 0..count-1=planets

      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        setFocusedIdx((prev) => {
          if (prev === null) return -1; // start at sun
          return prev < count - 1 ? prev + 1 : -1; // wrap to sun
        });
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        setFocusedIdx((prev) => {
          if (prev === null) return count - 1; // start at last planet
          return prev > -1 ? prev - 1 : count - 1; // wrap to last planet
        });
      } else if (e.key === 'Enter' || e.key === ' ') {
        if (focusedIdx === null) return;
        e.preventDefault();
        if (focusedIdx === -1) onSunClick();
        else if (focusedIdx >= 0 && focusedIdx < count) onPlanetClick(s.planets[focusedIdx].id);
      } else if (e.key === 'Escape') {
        setFocusedIdx(null);
      } else if (e.key === '+' || e.key === '=') {
        s.zoom = Math.min(2.4, s.zoom * 1.15);
        setZoomState(s.zoom);
      } else if (e.key === '-') {
        s.zoom = Math.max(0.4, s.zoom / 1.15);
        setZoomState(s.zoom);
      } else if (e.key === '0') {
        s.zoom = 1;
        setZoomState(1);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [focusedIdx, onPlanetClick, onSunClick]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const s = stateRef.current;
    const CX = rect.width / 2, CY = rect.height / 2;
    s.mouseX = CX + (sx - CX) / s.zoom;
    s.mouseY = CY + (sy - CY) / s.zoom;
  }, []);

  const handleMouseLeave = useCallback(() => {
    stateRef.current.mouseX = -1;
    stateRef.current.mouseY = -1;
    stateRef.current.hoverPlanet = null;
    stateRef.current.hoverSun = false;
    setHoverInfo(null);
    setSunHover(false);
  }, []);

  const handleClick = useCallback(() => {
    if (stateRef.current.hoverPlanet) onPlanetClick(stateRef.current.hoverPlanet.id);
    else if (stateRef.current.hoverSun) onSunClick();
  }, [onPlanetClick, onSunClick]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const dz = -e.deltaY * 0.0015;
    stateRef.current.zoom = Math.max(0.4, Math.min(2.4, stateRef.current.zoom * (1 + dz)));
    setZoomState(stateRef.current.zoom);
  }, []);

  const setZoom = useCallback((z: number) => {
    stateRef.current.zoom = Math.max(0.4, Math.min(2.4, z));
    setZoomState(stateRef.current.zoom);
  }, []);

  const cursor = (stateRef.current.hoverPlanet || stateRef.current.hoverSun) ? 'pointer' : 'default';

  const focusLabel = useMemo(() => {
    if (focusedIdx === null) return '';
    if (focusedIdx === -1) return 'Sun focused. Press Enter to open.';
    const p = stateRef.current.planets[focusedIdx];
    return p ? `${p.name} focused. ${p.dust} stardust, ${p.biomes} biomes. Press Enter to open.` : '';
  }, [focusedIdx]);

  return (
    <div ref={wrapRef} className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        tabIndex={0}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
        onWheel={handleWheel}
        className="w-full h-full block outline-none"
        style={{ cursor }}
        role="application"
        aria-label="Galaxy visualization. Use arrow keys to navigate planets, Enter to select."
        aria-roledescription="galaxy map"
      />
      <div aria-live="polite" className="sr-only">{focusLabel}</div>

      {/* Planet tooltip */}
      {hoverInfo && (
        <div
          className="absolute z-10 bg-[rgba(7,4,26,0.95)] backdrop-blur-sm border border-[var(--border)] rounded-lg px-3.5 py-3 pointer-events-none shadow-[0_16px_32px_rgba(0,0,0,0.5)] min-w-[200px]"
          style={{
            left: hoverInfo.cssX,
            top: hoverInfo.cssY,
            transform: 'translate(-50%, calc(-100% - 14px))',
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: hoverInfo.planet.color, boxShadow: `0 0 6px ${hoverInfo.planet.color}` }} />
            <span className="font-display text-sm font-medium text-[var(--text-1)]">{hoverInfo.planet.name}</span>
          </div>
          <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-1 text-[11px]">
            <dt className="text-[var(--text-3)]">Stardust</dt>
            <dd className="font-mono text-[var(--text-1)] text-right">{hoverInfo.planet.dust.toLocaleString()}</dd>
            <dt className="text-[var(--text-3)]">Biomes</dt>
            <dd className="font-mono text-[var(--text-1)] text-right">{hoverInfo.planet.biomes}</dd>
          </dl>
        </div>
      )}

      {/* Zoom controls */}
      <div className="absolute right-8 bottom-7 z-[6] flex flex-col gap-1.5 bg-[rgba(7,4,26,0.65)] border border-[var(--border-soft)] rounded-xl p-1.5 backdrop-blur-[10px]">
        <button
          onClick={() => setZoom(zoom * 1.2)}
          className="w-8 h-8 rounded-lg bg-transparent text-[var(--text-2)] hover:bg-[var(--surface-2)] hover:text-[var(--text-1)] flex items-center justify-center transition-colors duration-100"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <div className="font-mono text-[10px] text-[var(--text-3)] text-center py-0.5 border-y border-[var(--border-soft)] mx-0.5 select-none">
          {Math.round(zoom * 100)}%
        </div>
        <button
          onClick={() => setZoom(zoom / 1.2)}
          className="w-8 h-8 rounded-lg bg-transparent text-[var(--text-2)] hover:bg-[var(--surface-2)] hover:text-[var(--text-1)] flex items-center justify-center transition-colors duration-100"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <button
          onClick={() => setZoom(1)}
          className="w-8 h-8 rounded-lg bg-transparent text-[var(--text-2)] hover:bg-[var(--surface-2)] hover:text-[var(--text-1)] flex items-center justify-center transition-colors duration-100"
          title="Reset zoom (0)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 7V3h4"/><path d="M21 7V3h-4"/><path d="M3 17v4h4"/><path d="M21 17v4h-4"/></svg>
        </button>
      </div>
    </div>
  );
});
