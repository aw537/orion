import React, { useState, useEffect, useRef } from 'react';
import { Button } from '../ui';
import { apiClient } from '../../api/client';
import { useQueryClient } from '@tanstack/react-query';

const SWATCHES = ['#A78BFA', '#EC4899', '#F97316', '#14B8A6', '#6EE7B7', '#FCD34D', '#8B5CF6'];

interface Props { open: boolean; onClose: () => void }

export default function CreatePlanetModal({ open, onClose }: Props) {
  const [name, setName] = useState('');
  const [color, setColor] = useState(SWATCHES[0]);
  const inputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 60);
  }, [open]);

  if (!open) return null;

  const handleCreate = async () => {
    if (!name.trim()) return;
    try {
      await apiClient.post('/api/v1/planets', { name: name.trim(), color });
      qc.invalidateQueries({ queryKey: ['galaxy'] });
      onClose();
      setName('');
    } catch (err) {
      console.error('Planet creation failed:', err);
    }
  };

  return (
    <div
      className="absolute inset-0 z-[11] bg-[rgba(7,4,26,0.7)] backdrop-blur-sm flex items-center justify-center pointer-events-auto animate-[fade-in_220ms_ease-expo]"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-[540px] bg-gradient-to-b from-[rgba(45,27,105,0.5)] to-[rgba(45,27,105,0.3)] border border-[var(--border)] rounded-[14px] p-7 shadow-[0_30px_80px_rgba(0,0,0,0.55)]">
        <h3 className="font-display text-lg font-medium mb-1">Create a new Planet</h3>
        <p className="text-[var(--text-3)] text-xs mb-5">A Planet is a knowledge domain — a top-level region of your Galaxy.</p>

        <label className="block text-[10px] uppercase tracking-[0.1em] text-[var(--text-3)] mb-2 mt-3.5">Name</label>
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={40}
          className="w-full h-[42px] px-3.5 bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)] rounded-lg text-[var(--text-1)] font-display text-base outline-none focus:border-[var(--violet-300)] focus:bg-[rgba(124,58,237,0.10)] transition-all duration-150"
        />

        <label className="block text-[10px] uppercase tracking-[0.1em] text-[var(--text-3)] mb-2 mt-3.5">Color</label>
        <div className="flex gap-2 flex-wrap">
          {SWATCHES.map((c) => (
            <div
              key={c}
              onClick={() => setColor(c)}
              className="w-[30px] h-[30px] rounded-full cursor-pointer transition-transform duration-150 hover:scale-110"
              style={{
                background: c,
                boxShadow: `0 0 12px ${c}`,
                border: color === c ? '2px solid #fff' : '2px solid transparent',
                transform: color === c ? 'scale(1.12)' : undefined,
              }}
            />
          ))}
        </div>

        <div className="mt-4 p-4 bg-[rgba(0,0,0,0.25)] border border-[var(--border-soft)] rounded-[10px] flex items-center gap-4">
          <div
            className="w-[46px] h-[46px] rounded-full flex-shrink-0"
            style={{
              background: color,
              boxShadow: `0 0 24px ${color}, inset -6px -8px 12px rgba(0,0,0,0.35)`,
            }}
          />
          <div>
            <div className="font-display text-[15px] text-[var(--text-1)]">{name || 'New planet'}</div>
            <div className="text-[var(--text-3)] text-[11px] font-mono mt-1">orbit · auto · seed state · 0 stardust</div>
          </div>
        </div>

        <div className="flex justify-end gap-2.5 mt-5">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={handleCreate}>Add to Galaxy</Button>
        </div>
      </div>
    </div>
  );
}
