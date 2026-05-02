import { useState } from 'react';

interface InboxRowProps {
  record: {
    stardust: { id: string; content: string; region: string; created_at: string };
    suggestion: string | null;
    suggestion_confidence: number;
    suggestion_reasoning: string;
    original_reasoning: string | null;
  };
  planetNames: string[];
  routing?: boolean;
  onRoute: (planet: string, biome?: string) => void;
}

export function InboxRow({ record, planetNames, routing, onRoute }: InboxRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const pct = Math.round(record.suggestion_confidence * 100);
  const good = record.suggestion_confidence > 0.6;

  const regionColor = record.stardust.region === 'analytical'
    ? 'bg-[rgba(124,58,237,0.2)] text-[#A78BFA]'
    : record.stardust.region === 'procedural'
    ? 'bg-[rgba(14,165,233,0.2)] text-[#38BDF8]'
    : 'bg-[rgba(16,185,129,0.2)] text-[#6EE7B7]';

  return (
    <div className="border-b border-[rgba(196,181,253,0.1)] p-4 hover:bg-[rgba(124,58,237,0.05)] transition-colors">
      <div className="flex items-start gap-2 mb-2">
        <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${regionColor}`}>{record.stardust.region}</span>
        <p className="text-xs text-[#C4B5FD] leading-relaxed line-clamp-2 flex-1 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          {record.stardust.content}
        </p>
      </div>
      {expanded && <p className="text-xs text-[#C4B5FD] leading-relaxed mb-2 pl-1">{record.stardust.content}</p>}
      {record.suggestion && (
        <div className="mb-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-[#9484C2]">Suggested:</span>
            <span className="text-xs text-[#F3F0FF] font-medium">{record.suggestion}</span>
            <span className={`text-xs ml-auto ${pct > 75 ? 'text-[#6EE7B7]' : pct > 55 ? 'text-[#F59E0B]' : 'text-[#9484C2]'}`}>{pct}%</span>
          </div>
          <p className="text-xs text-[#9484C2] leading-relaxed">{record.suggestion_reasoning}</p>
        </div>
      )}
      <div className="flex gap-2">
        {good && record.suggestion && (
          <button onClick={() => onRoute(record.suggestion!)}
            disabled={routing}
            className="flex-1 text-xs py-1.5 rounded bg-[rgba(124,58,237,0.2)] text-[#A78BFA] hover:bg-[rgba(124,58,237,0.35)] transition-colors disabled:opacity-50">
            Route to {record.suggestion}
          </button>
        )}
        {choosing ? (
          <select
            autoFocus
            className="text-xs py-1.5 px-2 rounded border border-[rgba(196,181,253,0.3)] bg-[rgba(7,4,26,0.9)] text-[#C4B5FD] outline-none"
            defaultValue=""
            onChange={(e) => { if (e.target.value) onRoute(e.target.value); setChoosing(false); }}
            onBlur={() => setChoosing(false)}
          >
            <option value="" disabled>Select a planet...</option>
            {planetNames.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        ) : (
          <button onClick={() => setChoosing(true)}
            className="text-xs py-1.5 px-3 rounded border border-[rgba(196,181,253,0.2)] text-[#9484C2] hover:text-[#C4B5FD] hover:border-[rgba(196,181,253,0.4)] transition-colors">
            Choose
          </button>
        )}
      </div>
    </div>
  );
}
