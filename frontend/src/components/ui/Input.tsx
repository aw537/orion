import React from 'react';
import { clsx } from 'clsx';

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

export function Input({ error, className, ...props }: Props) {
  return (
    <input
      className={clsx(
        'h-9 px-3 rounded-lg bg-[var(--surface-3)] border border-[var(--border-soft)] text-[var(--text-1)] font-body text-[13px] outline-none w-full',
        'transition-all duration-150 ease-expo',
        'placeholder:text-[var(--text-3)]',
        'focus:border-[var(--violet-300)] focus:bg-[rgba(124,58,237,0.08)]',
        error && 'border-[var(--danger)]',
        className,
      )}
      {...props}
    />
  );
}
