import React from 'react';

export function OrionMark({ className }: { className?: string }) {
  return (
    <span className={`font-display inline-flex items-center gap-2 font-semibold tracking-[0.18em] text-xs text-[var(--text-1)] ${className || ''}`}>
      <span className="text-[var(--sun-core)] text-sm" style={{ textShadow: '0 0 12px rgba(245, 158, 11, 0.6)' }}>*</span>
      ORION
    </span>
  );
}
