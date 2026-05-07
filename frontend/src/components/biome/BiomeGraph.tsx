import React, { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';
import { useBiomeGraph } from '../../api/biomes';
import { theme } from '../../theme';
import { useNebulaStore } from '../../store/nebulaStore';
import { useNebulaStream } from '../../hooks/useNebulaStream';

const REGION_COLORS = theme.colors.region;
const ENTITY_COLORS = theme.colors.entity;

interface Props {
  biomeId: string;
  onNodeClick: (type: string, id: string) => void;
}

export default function BiomeGraph({ biomeId, onNodeClick }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { data: graphData } = useBiomeGraph(biomeId);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string; pills: string } | null>(null);
  const events = useNebulaStore((s) => s.events);
  useNebulaStream();

  useEffect(() => {
    if (!svgRef.current || !graphData) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const container = svgRef.current.parentElement!;
    const svgRect = svgRef.current.getBoundingClientRect();
    const W = svgRect.width || container.clientWidth;
    const H = (svgRect.height || container.clientHeight) - 44; // minus nebula strip
    svg.attr('viewBox', `0 0 ${W} ${H}`);

    // Backend returns { nodes, edges } where node.type = 'stardust' | 'entity'
    const nodes = (graphData.nodes || []).map((d: any) => ({
      ...d,
      kind: d.type,
      content: d.label,
      region: d.metadata?.region,
      confidence: d.metadata?.confidence ?? d.size,
      contradiction_id: null,
      name: d.label,
      entity_type: d.metadata?.entity_type,
      tier: d.size,
    }));
    const links = (graphData.edges || []).map((l: any) => ({
      ...l,
      kind: l.type === 'contradiction' ? 'contra'
          : l.type === 'co_chunk' ? 'co_chunk'
          : l.type === 'wikilink' ? 'wikilink'
          : 'rel',
    }));

    const stardustR = (d: any) => 8 + ((d.confidence || 0.5) - 0.5) * 24;
    const entitySize = (d: any) => 10 + ((d.tier || 1) - 1) * 4;

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d: any) => d.id)
        .distance((l: any) => l.kind === 'contra' ? 110 : l.kind === 'co_chunk' ? 50 : l.kind === 'wikilink' ? 90 : 70)
        .strength((l: any) => l.kind === 'contra' ? 0.3 : l.kind === 'co_chunk' ? 0.7 : l.kind === 'wikilink' ? 0.4 : 0.6))
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collide', d3.forceCollide((d: any) => d.kind === 'stardust' ? stardustR(d) + 6 : entitySize(d) + 14))
      .alpha(1).alphaDecay(0.025);

    const linkG = svg.append('g');
    const nodeG = svg.append('g');

    const link = linkG.selectAll('line').data(links).enter().append('line')
      .attr('stroke', (d: any) =>
        d.kind === 'contra'    ? 'rgba(245, 158, 11, 0.55)' :
        d.kind === 'co_chunk'  ? 'rgba(148, 163, 184, 0.18)' :
        d.kind === 'wikilink'  ? 'rgba(34, 211, 238, 0.45)' :
                                 'rgba(196, 181, 253, 0.22)')
      .attr('stroke-width', (d: any) => d.kind === 'contra' ? 1.5 : 1)
      .attr('stroke-dasharray', (d: any) =>
        d.kind === 'contra'   ? '5 4' :
        d.kind === 'co_chunk' ? '2 3' :
        null);

    const node = nodeG.selectAll('g').data(nodes).enter().append('g')
      .attr('class', 'cursor-pointer')
      .call(d3.drag<any, any>()
        .on('start', (e: any, d: any) => { if (!e.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', (e: any, d: any) => { d.fx = e.x; d.fy = e.y; })
        .on('end', (e: any, d: any) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

    // Stardust circles
    node.filter((d: any) => d.kind === 'stardust').each(function (d: any) {
      const g = d3.select(this);
      const r = stardustR(d);
      if (d.contradiction_id) {
        g.append('circle').attr('r', r + 5).attr('fill', 'none').attr('stroke', '#F59E0B').attr('stroke-width', 2).attr('stroke-dasharray', '3 3');
      }
      g.append('circle').attr('r', r)
        .attr('fill', REGION_COLORS[d.region] || '#7C3AED')
        .attr('fill-opacity', 0.4 + (d.confidence || 0.5) * 0.6)
        .attr('stroke', 'rgba(7,4,26,0.6)').attr('stroke-width', 1);
    });

    // Entity diamonds
    node.filter((d: any) => d.kind === 'entity').each(function (d: any) {
      const g = d3.select(this);
      const s = entitySize(d);
      g.append('rect').attr('x', -s / 2).attr('y', -s / 2).attr('width', s).attr('height', s)
        .attr('transform', 'rotate(45)')
        .attr('fill', ENTITY_COLORS[d.entity_type] || '#8B5CF6')
        .attr('stroke', 'rgba(7,4,26,0.7)').attr('stroke-width', 1);
      g.append('text').attr('x', s + 8).attr('y', 3)
        .attr('fill', 'var(--text-3)').attr('font-size', '10px').attr('font-family', 'JetBrains Mono, monospace')
        .text(d.name);
    });

    // Hover
    node.on('mouseenter', function (e: any, d: any) {
      const rect = (this as SVGGElement).getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();
      const content = d.kind === 'stardust'
        ? (d.content || '').slice(0, 120) + ((d.content || '').length > 120 ? '…' : '')
        : `Tier ${d.tier || 1} · ${d.name}`;
      const pills = d.kind === 'stardust' ? (d.region || 'contextual') : (d.entity_type || 'concept');
      setTooltip({ x: rect.left - containerRect.left + rect.width / 2, y: rect.top - containerRect.top + 4, content, pills });
    });
    node.on('mouseleave', () => setTooltip(null));
    node.on('click', (e: any, d: any) => {
      onNodeClick(d.kind === 'stardust' ? 'stardust' : 'entity', d.id);
    });

    sim.on('tick', () => {
      link.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y);
      node.attr('transform', (d: any) => `translate(${d.x}, ${d.y})`);
    });

    return () => { sim.stop(); };
  }, [graphData, biomeId, onNodeClick]);

  // Supersession animation: react to SUPERSESSION events from nebulaStore
  useEffect(() => {
    if (!svgRef.current || events.length === 0) return;
    const latest = events[0];
    if (latest.action_type === 'SUPERSESSION' && latest.record_id) {
      const svg = d3.select(svgRef.current);
      svg.selectAll('g').filter((d: unknown) => (d as { id?: string })?.id === latest.record_id)
        .transition().duration(1000).style('opacity', 0.15);
      try {
        const payload = typeof latest.payload_after === 'string' ? JSON.parse(latest.payload_after) : latest.payload_after;
        if (payload?.superseded_by) {
          const newNode = svg.selectAll('g').filter((d: unknown) => (d as { id?: string })?.id === payload.superseded_by);
          newNode.append('circle').attr('r', 20).attr('fill', 'none')
            .attr('stroke', '#F59E0B').attr('stroke-width', 1.5).attr('stroke-dasharray', '4 3')
            .transition().duration(2000).style('opacity', 0).remove();
        }
      } catch (err) {
        console.error('Supersession animation failed:', err);
      }
    }
  }, [events.length]);

  return (
    <div className="relative w-full h-full">
      <svg ref={svgRef} className="w-full h-full block cursor-grab active:cursor-grabbing" role="img" aria-label="Biome graph showing stardust and entity relationships" />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-10 pointer-events-none bg-[rgba(7,4,26,0.96)] border border-[var(--border)] rounded-lg px-3 py-2.5 min-w-[240px] max-w-[320px] shadow-[0_16px_32px_rgba(0,0,0,0.5)]"
          style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, calc(-100% - 14px))' }}
        >
          <div className="flex items-center gap-1.5 mb-2 flex-wrap">
            <span className="inline-flex items-center gap-1 px-[7px] py-px rounded-full text-[9px] font-semibold uppercase tracking-[0.08em] border"
              style={{ color: REGION_COLORS[tooltip.pills] || ENTITY_COLORS[tooltip.pills] || '#7C3AED', background: `${REGION_COLORS[tooltip.pills] || ENTITY_COLORS[tooltip.pills] || '#7C3AED'}26`, borderColor: `${REGION_COLORS[tooltip.pills] || ENTITY_COLORS[tooltip.pills] || '#7C3AED'}55` }}>
              <span className="w-[5px] h-[5px] rounded-full bg-current" />
              {tooltip.pills}
            </span>
          </div>
          <div className="text-xs text-[var(--text-1)] leading-relaxed">{tooltip.content}</div>
        </div>
      )}

      {/* Bottom nebula strip */}
      <div className="absolute left-0 right-0 bottom-0 h-11 px-6 flex items-center gap-2.5 bg-[rgba(7,4,26,0.85)] backdrop-blur-[12px] border-t border-[var(--border-soft)] z-[4]">
        <span className="inline-flex items-center gap-2 text-[11px] text-[var(--text-3)] uppercase tracking-[0.08em] pr-3.5 border-r border-[var(--border-soft)] h-6">
          <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] shadow-[0_0_8px_#34D399] animate-[pulse-dot_2s_ease-in-out_infinite]" />
          Nebula
        </span>
      </div>
    </div>
  );
}
