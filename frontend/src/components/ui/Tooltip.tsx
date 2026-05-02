import React from 'react';
import { clsx } from 'clsx';

interface Props {
  visible: boolean;
  x: number;
  y: number;
  children: React.ReactNode;
  className?: string;
}

export function Tooltip({ visible, x, y, children, className }: Props) {
  return (
    <div
      className={clsx(
        'absolute z-10 bg-[rgba(7,4,26,0.95)] border border-[var(--border-soft)] rounded-md px-2.5 py-2',
        'text-[11px] text-[var(--text-1)] shadow-[0_8px_24px_rgba(0,0,0,0.6)] pointer-events-none whitespace-nowrap',
        'transition-opacity duration-150 ease-expo',
        visible ? 'opacity-100' : 'opacity-0',
        className,
      )}
      style={{ left: x, top: y, transform: 'translate(-50%, calc(-100% - 14px))' }}
    >
      {children}
    </div>
  );
}
