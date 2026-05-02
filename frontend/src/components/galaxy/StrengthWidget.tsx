import React from 'react';
import { useGalaxyStrength, useGalaxyStatus } from '../../api/galaxy';
import { OrionMark } from '../ui';

interface Props {
  expanded: boolean;
  onToggle: () => void;
}

export default function StrengthWidget({ expanded, onToggle }: Props) {
  const { data: strength } = useGalaxyStrength();
  const { data: status } = useGalaxyStatus();
  const score = strength?.score ?? 0;
  const trend = strength?.trend ?? '';
  const delta = strength?.delta ?? null;

  return (
    <div className="text-[var(--text-1)] cursor-pointer select-none" onClick={onToggle}>
      <div className="flex items-center gap-2.5 mb-7">
        <OrionMark />
      </div>
      <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-[var(--text-3)] mb-2">Galaxy strength</div>
      <div className="h-px bg-gradient-to-r from-[var(--violet-300)] to-transparent opacity-50 mb-2" />
      <div className="font-mono text-[28px] font-medium text-[var(--text-1)] tracking-tight leading-none mb-1.5">
        {Math.round(score).toLocaleString()}
      </div>
      {delta != null && (
        <div className={`font-mono text-[11px] mb-1 ${delta >= 0 ? 'text-[#34D399]' : 'text-[#F87171]'}`}>
          {delta >= 0 ? '+' : ''}{delta}
        </div>
      )}
      {trend && !delta && <div className="font-mono text-[11px] text-[#34D399] mb-1">{trend}</div>}
      {status && (
        <div className="mt-3 space-y-1">
          {[
            { l: 'Stardust', v: (status.total_stardust ?? 0).toLocaleString() },
            { l: 'Entities', v: (status.total_entities ?? 0).toLocaleString() },
          ].map((row) => (
            <div key={row.l} className="flex items-center justify-between gap-6">
              <span className="text-[10px] text-[var(--text-3)]">{row.l}</span>
              <span className="font-mono text-[11px] text-[var(--text-2)]">{row.v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
