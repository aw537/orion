import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import * as d3 from 'd3';
import { useFullGraph, useEntityNeighborhood, useUnlinkedMentions, linkAll, type GraphEntity, type GraphEdge, type PlanetInfo } from '../api/graph';

/* ── Edge colors by relationship type ─────────────────────────────── */
const EDGE_COLORS: Record<string, string> = {
  USES: '#ffffff', REPLACES: '#ffffff', EVALUATES: '#ffffff',
  DEPENDS_ON: '#ffffff', WORKS_WITH: '#ffffff', PART_OF: '#ffffff',
  INFORMS: '#ffffff', INDIRECTLY_USES: '#ffffff', DERIVED_FROM: '#ffffff',
  SUPERSEDES: '#ffffff',
};
const DEFAULT_EDGE = '#ffffff';

/* ── D3 node type (extends GraphEntity with simulation coords) ──── */
interface SimNode extends d3.SimulationNodeDatum, GraphEntity {}
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  type: string;
  confidence: number;
  strength: number;
}

/* ── Node radius from tier + degree ─────────────────────────────── */
function nodeRadius(d: SimNode): number {
  return Math.max(4, 3 + d.tier * 2 + Math.sqrt(d.degree) * 1.5);
}

/* ═══════════════════════════════════════════════════════════════════ */
export default function KnowledgeGraphView() {
  const navigate = useNavigate();
  const svgRef = useRef<SVGSVGElement>(null);
  const { data: graph, isLoading } = useFullGraph();
  const { data: unlinked } = useUnlinkedMentions();

  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [hoveredEntity, setHoveredEntity] = useState<SimNode | null>(null);
  const [activePlanets, setActivePlanets] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [linking, setLinking] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearchQuery(searchQuery), 300);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const { data: neighborhood } = useEntityNeighborhood(selectedEntity);

  /* ── Toggle planet filter ──────────────────────────────────────── */
  const togglePlanet = useCallback((planetId: string) => {
    setActivePlanets(prev => {
      const next = new Set(prev);
      if (next.has(planetId)) next.delete(planetId); else next.add(planetId);
      return next;
    });
  }, []);

  /* ── D3 force simulation ───────────────────────────────────────── */
  useEffect(() => {
    if (!graph || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    /* Filter by active planets */
    const showAll = activePlanets.size === 0;
    const visibleEntities = graph.entities.filter(e =>
      (showAll || (e.planet_id && activePlanets.has(e.planet_id))) &&
      (!debouncedSearchQuery || e.name.toLowerCase().includes(debouncedSearchQuery.toLowerCase()))
    );
    const visibleIds = new Set(visibleEntities.map(e => e.id));
    const visibleEdges = graph.edges.filter(e => visibleIds.has(e.source as string) && visibleIds.has(e.target as string));

    const nodes: SimNode[] = visibleEntities.map(e => ({ ...e }));
    const links: SimLink[] = visibleEdges.map(e => ({ ...e, source: e.source, target: e.target }));

    /* Container with zoom */
    const g = svg.append('g');
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    /* Simulation */
    const simulation = d3.forceSimulation<SimNode>(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links).id(d => d.id).distance(80).strength(l => 0.3 + l.confidence * 0.4))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<SimNode>().radius(d => nodeRadius(d) + 4))
      .force('x', d3.forceX(width / 2).strength(0.03))
      .force('y', d3.forceY(height / 2).strength(0.03));

    /* Edges */
    const link = g.append('g').attr('class', 'links')
      .selectAll('line').data(links).join('line')
      .attr('stroke', d => EDGE_COLORS[d.type] || DEFAULT_EDGE)
      .attr('stroke-opacity', d => 0.2 + d.confidence * 0.4)
      .attr('stroke-width', d => 0.5 + d.strength * 0.5);

    /* Nodes */
    const node = g.append('g').attr('class', 'nodes')
      .selectAll<SVGCircleElement, SimNode>('circle').data(nodes).join('circle')
      .attr('r', d => nodeRadius(d))
      .attr('fill', d => d.planet_color || '#6B7280')
      .attr('stroke', d => d.id === selectedEntity ? '#fff' : 'rgba(255,255,255,0.15)')
      .attr('stroke-width', d => d.id === selectedEntity ? 2 : 0.5)
      .attr('cursor', 'pointer')
      .on('click', (_event, d) => setSelectedEntity(prev => prev === d.id ? null : d.id))
      .on('mouseenter', (_event, d) => setHoveredEntity(d))
      .on('mouseleave', () => setHoveredEntity(null))
      .call(d3.drag<SVGCircleElement, SimNode>()
        .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    /* Labels — only for tier >= 2 or degree >= 3 */
    const label = g.append('g').attr('class', 'labels')
      .selectAll('text').data(nodes.filter(n => n.tier >= 2 || n.degree >= 3)).join('text')
      .text(d => d.name)
      .attr('font-size', d => d.tier >= 3 ? 11 : 9)
      .attr('fill', 'rgba(226,232,240,0.8)')
      .attr('text-anchor', 'middle')
      .attr('dy', d => nodeRadius(d) + 12)
      .attr('pointer-events', 'none');

    /* Tick */
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x!)
        .attr('y1', d => (d.source as SimNode).y!)
        .attr('x2', d => (d.target as SimNode).x!)
        .attr('y2', d => (d.target as SimNode).y!);
      node.attr('cx', d => d.x!).attr('cy', d => d.y!);
      label.attr('x', d => d.x!).attr('y', d => d.y!);
    });

    /* Highlight neighborhood when entity selected */
    if (neighborhood && selectedEntity) {
      const neighborIds = new Set(neighborhood.entities.map(e => e.id));
      node.attr('opacity', d => neighborIds.has(d.id) ? 1 : 0.15);
      link.attr('opacity', d => {
        const s = (d.source as SimNode).id, t = (d.target as SimNode).id;
        return neighborIds.has(s) && neighborIds.has(t) ? 1 : 0.05;
      });
      label.attr('opacity', d => neighborIds.has(d.id) ? 1 : 0.1);
    }

    /* Initial zoom to fit */
    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.8).translate(-width / 2, -height / 2));

    return () => { simulation.stop(); };
  }, [graph, activePlanets, debouncedSearchQuery, selectedEntity, neighborhood]);

  const handleLinkAll = async (entityId: string) => {
    setLinking(entityId);
    try { await linkAll(entityId); } catch { /* noop */ } finally { setLinking(null); }
  };

  if (isLoading) return <div className="flex items-center justify-center h-screen text-[var(--text-3)]">Loading graph…</div>;

  const planets = graph?.planets ?? [];
  const entityCount = graph?.entities.length ?? 0;
  const edgeCount = graph?.edges.length ?? 0;

  return (
    <div className="h-full bg-[#07041A] flex">
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside className="w-60 flex-shrink-0 border-r border-[var(--border-soft)] bg-[rgba(7,4,26,0.9)] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-3 border-b border-[var(--border-soft)]">
          <h1 className="text-sm font-medium text-[var(--text-1)]">Knowledge Graph</h1>
          <p className="text-[10px] text-[var(--text-3)] mt-0.5">{entityCount} entities · {edgeCount} edges</p>
        </div>

        {/* Search */}
        <div className="p-3 border-b border-[var(--border-soft)]">
          <input
            type="text" placeholder="Search entities…" value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full bg-[rgba(255,255,255,0.05)] border border-[var(--border-soft)] rounded px-2 py-1 text-xs text-[var(--text-1)] placeholder:text-[var(--text-3)] outline-none focus:border-violet-500/50"
          />
        </div>

        {/* Planet filters */}
        <div className="p-3 border-b border-[var(--border-soft)]">
          <h3 className="text-[10px] font-medium text-[var(--text-3)] uppercase tracking-wider mb-2">Planets</h3>
          {planets.map(p => {
            const active = activePlanets.size === 0 || activePlanets.has(p.id);
            return (
              <button key={p.id} onClick={() => togglePlanet(p.id)}
                className={`flex items-center gap-2 w-full text-left px-1.5 py-1 rounded text-xs transition-opacity ${active ? 'opacity-100' : 'opacity-40'}`}>
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: p.color }} />
                <span className="text-[var(--text-1)] truncate">{p.name}</span>
              </button>
            );
          })}
          {activePlanets.size > 0 && (
            <button onClick={() => setActivePlanets(new Set())} className="text-[10px] text-violet-400 hover:text-violet-300 mt-1">Show all</button>
          )}
        </div>

        {/* Edge legend */}
        <div className="p-3 border-b border-[var(--border-soft)]">
          <h3 className="text-[10px] font-medium text-[var(--text-3)] uppercase tracking-wider mb-2">Relationships</h3>
          <div className="space-y-0.5">
            {Object.entries(EDGE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5 text-[10px] text-[var(--text-3)]">
                <span className="w-3 h-0.5 rounded flex-shrink-0" style={{ background: color }} />
                {type}
              </div>
            ))}
          </div>
        </div>

        {/* Unlinked mentions */}
        {unlinked && unlinked.length > 0 && (
          <div className="p-3 flex-1 overflow-y-auto">
            <h3 className="text-[10px] font-medium text-amber-400 uppercase tracking-wider mb-2">Unlinked</h3>
            {unlinked.slice(0, 8).map(m => (
              <div key={m.entity_id} className="flex items-center justify-between py-0.5">
                <span className="text-[10px] text-[var(--text-1)] truncate">{m.entity_name} <span className="text-[var(--text-3)]">{m.unlinked_count}</span></span>
                <button onClick={() => handleLinkAll(m.entity_id)} disabled={linking === m.entity_id}
                  className="text-[9px] text-violet-400 hover:text-violet-300 disabled:opacity-50 flex-shrink-0 ml-1">
                  {linking === m.entity_id ? '…' : 'Link'}
                </button>
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* ── Graph canvas ─────────────────────────────────────────── */}
      <div className="flex-1 relative">
        <svg ref={svgRef} className="w-full h-full" role="img" aria-label="Knowledge graph visualization" />

        {/* Tooltip */}
        {hoveredEntity && (
          <div className="absolute top-4 right-4 bg-[rgba(7,4,26,0.92)] border border-[var(--border-soft)] rounded-lg p-3 backdrop-blur-sm pointer-events-none max-w-xs"
            role="tooltip">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: hoveredEntity.planet_color }} />
              <span className="text-sm font-medium text-[var(--text-1)]">{hoveredEntity.name}</span>
            </div>
            <div className="text-[10px] text-[var(--text-3)] space-y-0.5">
              <div>Type: <span className="text-[var(--text-2)]">{hoveredEntity.type}</span></div>
              <div>Tier: <span className="text-[var(--text-2)]">{hoveredEntity.tier}</span> · Degree: <span className="text-[var(--text-2)]">{hoveredEntity.degree}</span></div>
              {hoveredEntity.planet_name && <div>Planet: <span className="text-[var(--text-2)]">{hoveredEntity.planet_name}</span></div>}
              <div>Mentions: <span className="text-[var(--text-2)]">{hoveredEntity.mentions}</span></div>
            </div>
          </div>
        )}

        {/* Selected entity detail */}
        {selectedEntity && neighborhood && (
          <div className="absolute bottom-4 right-4 bg-[rgba(7,4,26,0.92)] border border-[var(--border-soft)] rounded-lg p-3 backdrop-blur-sm max-w-xs">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-[var(--text-1)]">
                {neighborhood.entities.find(e => e.id === selectedEntity)?.name ?? 'Entity'}
              </span>
              <button onClick={() => setSelectedEntity(null)} className="text-[10px] text-[var(--text-3)] hover:text-[var(--text-1)]" aria-label="Close">&times;</button>
            </div>
            <div className="text-[10px] text-[var(--text-3)]">
              {neighborhood.entities.length} connected entities · {neighborhood.edges.length} edges (depth {neighborhood.depth})
            </div>
            <div className="mt-2 space-y-0.5 max-h-32 overflow-y-auto">
              {neighborhood.entities.filter(e => e.id !== selectedEntity).slice(0, 10).map(e => (
                <button key={e.id} onClick={() => setSelectedEntity(e.id)}
                  className="flex items-center gap-1.5 text-[10px] text-[var(--text-2)] hover:text-[var(--text-1)] w-full text-left">
                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: e.planet_color }} />
                  {e.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Controls hint */}
        <div className="absolute bottom-4 left-4 text-[10px] text-[var(--text-3)] opacity-60">
          Scroll to zoom · Drag to pan · Click node to focus · Drag node to reposition
        </div>
      </div>
    </div>
  );
}
