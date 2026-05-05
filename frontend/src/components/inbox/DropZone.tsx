import React, { useState, useRef, useCallback } from 'react';

const ALLOWED = ['.md', '.txt', '.yaml', '.yml', '.json'];

interface DropZoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export function DropZone({ onFiles, disabled }: DropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList || disabled) return;
    onFiles(Array.from(fileList));
  }, [onFiles, disabled]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={() => !disabled && fileRef.current?.click()}
      className={`w-full max-w-xl aspect-[4/3] rounded-2xl border-2 border-dashed flex flex-col items-center justify-center gap-4 transition-all duration-200 ${
        disabled ? 'opacity-50 cursor-not-allowed' :
        dragOver
          ? 'border-[#F59E0B] bg-[rgba(245,158,11,0.08)] shadow-[0_0_40px_rgba(245,158,11,0.15)] cursor-pointer'
          : 'border-[var(--border-soft)] hover:border-[rgba(196,181,253,0.4)] hover:bg-[rgba(124,58,237,0.04)] cursor-pointer'
      }`}
    >
      <div className={`text-4xl transition-transform duration-200 ${dragOver ? 'scale-110' : ''}`}>
        {dragOver ? '✦' : '↓'}
      </div>
      <p className="text-sm text-[var(--text-2)]">
        {dragOver ? 'Release to upload' : 'Drag & drop files here'}
      </p>
      <p className="text-xs text-[var(--text-3)]">or click to browse</p>
      <p className="text-xs text-[var(--text-3)] mt-2">
        Supported: {ALLOWED.join(', ')}
      </p>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept={ALLOWED.join(',')}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
