import React from 'react';

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export function NavButton({ children, className, ...props }: Props) {
  return (
    <button
      className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-full bg-[rgba(45,27,105,0.6)] border border-[var(--border)] text-[var(--text-1)] text-xs font-medium cursor-pointer backdrop-blur-sm hover:bg-[rgba(45,27,105,0.85)] transition-all duration-150 ${className || ''}`}
      {...props}
    >
      {children}
    </button>
  );
}
