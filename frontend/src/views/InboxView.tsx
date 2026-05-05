import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInboxUpload, useInboxHistory } from '../api/inbox';
import { DropZone } from '../components/inbox/DropZone';
import { IngestionResults } from '../components/inbox/IngestionResults';

interface FileUpload {
  file: File;
  status: 'pending' | 'uploading' | 'done' | 'error';
  result?: any;
  error?: string;
}

export default function InboxView() {
  const navigate = useNavigate();
  const upload = useInboxUpload();
  const { data: history } = useInboxHistory();
  const [uploads, setUploads] = useState<FileUpload[]>([]);

  const handleFiles = useCallback((files: File[]) => {
    const newUploads: FileUpload[] = files.map(f => ({ file: f, status: 'pending' }));
    setUploads(prev => [...newUploads, ...prev]);

    files.forEach((file, idx) => {
      setUploads(prev => prev.map((u, i) => i === idx ? { ...u, status: 'uploading' } : u));
      upload.mutateAsync(file).then(result => {
        setUploads(prev => prev.map(u => u.file === file ? { ...u, status: 'done', result } : u));
      }).catch(err => {
        setUploads(prev => prev.map(u => u.file === file ? { ...u, status: 'error', error: (err as Error).message } : u));
      });
    });
  }, [upload]);

  const activeUploads = uploads.filter(u => u.status === 'uploading');
  const completedUploads = uploads.filter(u => u.status === 'done');

  return (
    <div className="h-full flex flex-col bg-[var(--bg)]">
      {/* Header */}
      <div className="flex items-center gap-3 px-8 py-6 border-b border-[var(--border-soft)]">
        <button onClick={() => navigate('/')} className="text-[var(--text-3)] hover:text-[var(--text-1)] text-sm">← Galaxy</button>
        <h1 className="text-lg font-semibold text-[var(--text-1)]">Inbox</h1>
        <span className="text-xs text-[var(--text-3)]">Drop files to distribute knowledge across your Galaxy</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Drop zone */}
        <div className="flex items-center justify-center p-8">
          <DropZone onFiles={handleFiles} disabled={activeUploads.length > 0} />
        </div>

        {/* Per-file progress */}
        {uploads.length > 0 && (
          <div className="px-8 pb-4 space-y-2">
            {uploads.map((u, i) => (
              <div key={i} className="flex items-center gap-3 text-xs">
                <span className="text-[var(--text-2)] truncate flex-1">{u.file.name}</span>
                {u.status === 'uploading' && (
                  <span className="text-[#F59E0B] flex items-center gap-1">
                    <span className="w-3 h-3 border-2 border-[#F59E0B] border-t-transparent rounded-full animate-spin" />
                    Processing
                  </span>
                )}
                {u.status === 'done' && (
                  <span className="text-[#6EE7B7]">✓ {u.result?.chunks_routed} chunks routed</span>
                )}
                {u.status === 'error' && (
                  <span className="text-red-400">✗ {u.error}</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Results tables */}
        {completedUploads.length > 0 && (
          <div className="px-8 pb-6 space-y-4">
            {completedUploads.map((u, i) => (
              <IngestionResults
                key={i}
                filename={u.result.filename}
                results={u.result.results}
                chunksTotal={u.result.chunks_total}
                chunksRouted={u.result.chunks_routed}
              />
            ))}
          </div>
        )}

        {/* History */}
        {history?.items?.length > 0 && (
          <div className="px-8 py-4 border-t border-[var(--border-soft)]">
            <p className="text-xs text-[var(--text-3)] mb-2">Recent uploads</p>
            <div className="space-y-1">
              {history.items.slice(0, 10).map((h: any) => (
                <div key={h.ingestion_id} className="flex items-center gap-2 text-xs text-[var(--text-3)]">
                  <span className="text-[var(--text-2)]">{h.filename}</span>
                  <span>{h.chunks_routed} chunks</span>
                  <span className="ml-auto">{new Date(h.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
