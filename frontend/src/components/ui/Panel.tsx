import React, { forwardRef } from 'react';
import { clsx } from 'clsx';

interface Props {
  children: React.ReactNode;
  className?: string;
  side?: 'left' | 'right';
  width?: 'sm' | 'md' | 'lg';
  open?: boolean;
}

const WIDTHS = { sm: 'w-full sm:w-[320px]', md: 'w-full sm:w-[380px]', lg: 'w-full sm:w-[420px]' } as const;

export const Panel = forwardRef<HTMLDivElement, Props>(function Panel(
  { children, className, side = 'right', width = 'md', open = true },
  ref,
) {
  return (
    <div
      ref={ref}
      className={clsx(
        'absolute top-0 bottom-0 z-[10] bg-[rgba(7,4,26,0.96)] backdrop-blur-[20px] flex flex-col pointer-events-auto',
        side === 'right' ? 'right-0 border-l' : 'left-0 border-r',
        'border-[var(--border-soft)]',
        WIDTHS[width],
        open ? 'animate-[panel-in_280ms_var(--ease-out-expo)]' : 'translate-x-full',
        className,
      )}
    >
      {children}
    </div>
  );
});
