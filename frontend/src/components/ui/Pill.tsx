import React from 'react';
import { clsx } from 'clsx';

interface Props {
  color?: string;
  children: React.ReactNode;
  className?: string;
}

export function Pill({ color, children, className }: Props) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 h-[22px] px-2 rounded-full font-body text-[11px] font-medium tracking-[0.04em] uppercase',
        'bg-[var(--surface-3)] text-[var(--text-2)] border border-[var(--border-soft)] whitespace-nowrap',
        className,
      )}
    >
      {color && (
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
      )}
      {children}
    </span>
  );
}
