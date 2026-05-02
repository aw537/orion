import React from 'react';
import { clsx } from 'clsx';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

const variants: Record<Variant, string> = {
  primary: 'bg-[var(--violet-700)] text-white border-[var(--violet-700)] hover:bg-[#8B47F0] hover:border-[#8B47F0]',
  secondary: 'bg-[var(--surface-1)] border-[var(--border)] text-[var(--text-1)] hover:bg-[rgba(45,27,105,0.6)] hover:border-[rgba(196,181,253,0.35)]',
  ghost: 'bg-transparent text-[var(--text-2)] border-[var(--border-soft)] hover:text-[var(--text-1)] hover:border-[var(--border)] hover:bg-[var(--surface-2)]',
  danger: 'bg-transparent text-[var(--danger)] border-[rgba(220,38,38,0.4)] hover:bg-[rgba(220,38,38,0.1)]',
};

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  kbd?: string;
}

export function Button({ variant = 'primary', kbd, className, children, ...props }: Props) {
  return (
    <button
      className={clsx(
        'inline-flex items-center gap-2 h-8 px-3.5 rounded-lg font-body text-[13px] font-medium border cursor-pointer whitespace-nowrap transition-all duration-150 ease-expo',
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
      {kbd && (
        <span className="inline-flex items-center h-[18px] px-[5px] rounded bg-[rgba(255,255,255,0.06)] border border-[var(--border-soft)] font-mono text-[10px] text-[var(--text-2)] ml-0.5">
          {kbd}
        </span>
      )}
    </button>
  );
}
