interface RoutingResult {
  chunk_preview: string;
  target_planet_id: string;
  target_planet_name: string;
  target_biome_id: string | null;
  target_biome_name: string | null;
  confidence: number;
  method: string;
}

interface IngestionResultsProps {
  filename: string;
  results: RoutingResult[];
  chunksTotal: number;
  chunksRouted: number;
}

export function IngestionResults({ filename, results, chunksTotal, chunksRouted }: IngestionResultsProps) {
  if (!results.length) return null;

  return (
    <div className="border border-[var(--border-soft)] rounded-lg overflow-hidden">
      <div className="px-4 py-2.5 bg-[rgba(124,58,237,0.06)] border-b border-[var(--border-soft)] flex items-center justify-between">
        <span className="text-xs text-[var(--text-1)] font-medium">{filename}</span>
        <span className="text-xs text-[var(--text-3)]">{chunksRouted}/{chunksTotal} chunks routed</span>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--border-soft)] text-[var(--text-3)]">
            <th className="text-left px-4 py-2 font-medium">Content</th>
            <th className="text-left px-4 py-2 font-medium w-32">Planet</th>
            <th className="text-left px-4 py-2 font-medium w-32">Biome</th>
            <th className="text-right px-4 py-2 font-medium w-16">Conf.</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i} className="border-b border-[var(--border-soft)] last:border-0 hover:bg-[rgba(124,58,237,0.04)]">
              <td className="px-4 py-2 text-[var(--text-2)] truncate max-w-[300px]">{r.chunk_preview}</td>
              <td className="px-4 py-2">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#7C3AED]" />
                  <span className="text-[var(--text-1)]">{r.target_planet_name}</span>
                </span>
              </td>
              <td className="px-4 py-2 text-[var(--text-3)]">{r.target_biome_name || '—'}</td>
              <td className="px-4 py-2 text-right text-[var(--text-3)]">{Math.round(r.confidence * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
