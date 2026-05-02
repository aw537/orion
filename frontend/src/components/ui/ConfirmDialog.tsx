import React from 'react';

interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', onConfirm, onCancel }: Props) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[50] flex items-center justify-center" onClick={onCancel}>
      <div className="absolute inset-0 bg-[rgba(7,4,26,0.8)] backdrop-blur-sm" />
      <div
        className="relative bg-[rgba(7,4,26,0.96)] border border-[var(--border)] rounded-xl p-6 w-[380px] max-w-[90vw] shadow-[0_24px_48px_rgba(0,0,0,0.5)] animate-[rise_200ms_var(--ease-out-expo)]"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-display text-sm font-medium text-[var(--text-1)] mb-2">{title}</h3>
        <p className="text-xs text-[var(--text-3)] mb-5 leading-relaxed">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-xs text-[var(--text-2)] border border-[var(--border-soft)] hover:text-[var(--text-1)] hover:border-[var(--border)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 rounded-lg text-xs text-white bg-[var(--danger)] hover:brightness-110 transition-all"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
