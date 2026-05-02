import React, { useState } from 'react';
import { proposeMerge, acceptMerge, rejectMerge, executeMerge, getMergeProposal, getMergeSunPreview, getMergeEntityMappings, type MergeProposal } from '../../api/brain';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { Panel } from '../ui';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function MergePanel({ open, onClose }: Props) {
  const [targetGalaxyId, setTargetGalaxyId] = useState('');
  const [proposalId, setProposalId] = useState('');
  const [proposal, setProposal] = useState<MergeProposal | null>(null);
  const [sunPreview, setSunPreview] = useState<Record<string, any> | null>(null);
  const [entityMappings, setEntityMappings] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<any>(null);
  const trapRef = useFocusTrap<HTMLDivElement>(open);

  if (!open) return null;

  async function handlePropose() {
    if (!targetGalaxyId.trim()) return;
    setLoading(true); setError('');
    try {
      const res = await proposeMerge(targetGalaxyId.trim());
      setProposalId(res.proposal_id);
      await loadProposal(res.proposal_id);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  async function handleLoadProposal() {
    if (!proposalId.trim()) return;
    setLoading(true); setError('');
    await loadProposal(proposalId.trim());
    setLoading(false);
  }

  async function loadProposal(id: string) {
    try {
      const p = await getMergeProposal(id);
      setProposal(p);
      setProposalId(id);
    } catch (e: any) { setError(e.message); }
  }

  async function handleAccept() {
    if (!proposalId) return;
    setLoading(true); setError('');
    try {
      await acceptMerge(proposalId);
      await loadProposal(proposalId);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  async function handleReject() {
    if (!proposalId) return;
    setLoading(true); setError('');
    try {
      await rejectMerge(proposalId, 'Rejected from UI');
      await loadProposal(proposalId);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  async function handlePreviewSun() {
    if (!proposalId) return;
    setLoading(true); setError('');
    try {
      const preview = await getMergeSunPreview(proposalId);
      setSunPreview(preview);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  async function handlePreviewEntities() {
    if (!proposalId) return;
    setLoading(true); setError('');
    try {
      const mappings = await getMergeEntityMappings(proposalId);
      setEntityMappings(mappings);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  async function handleExecute() {
    if (!proposalId) return;
    setLoading(true); setError('');
    try {
      const res = await executeMerge(proposalId);
      setResult(res);
      await loadProposal(proposalId);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  const STATUS_COLORS: Record<string, string> = {
    proposed: '#F59E0B', accepted: '#3B82F6', sun_negotiation: '#8B5CF6',
    entity_reconciliation: '#8B5CF6', bridging: '#8B5CF6', complete: '#10B981', rejected: '#EF4444',
  };

  return (
    <Panel ref={trapRef} width="lg" open={open}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-soft)]">
        <div className="flex items-center gap-2">
          <span className="text-base"></span>
          <span className="text-sm font-semibold text-[var(--text-1)]">Galaxy Merge</span>
        </div>
        <button onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--text-1)] text-lg" aria-label="Close">×</button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* Propose or load */}
        {!proposal && (
          <>
            <div>
              <label className="text-xs text-[var(--text-2)] block mb-1.5">Propose merge with Galaxy ID</label>
              <div className="flex gap-2">
                <input
                  value={targetGalaxyId} onChange={(e) => setTargetGalaxyId(e.target.value)}
                  placeholder="Target Galaxy ID"
                  className="flex-1 bg-[rgba(255,255,255,0.05)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-1)] outline-none focus:border-[var(--accent)]"
                />
                <button onClick={handlePropose} disabled={loading} className="px-3 py-2 bg-[var(--accent)] text-white text-xs rounded-lg hover:opacity-90 disabled:opacity-50">
                  Propose
                </button>
              </div>
            </div>
            <div className="text-xs text-[var(--text-3)] text-center">— or —</div>
            <div>
              <label className="text-xs text-[var(--text-2)] block mb-1.5">Load existing proposal</label>
              <div className="flex gap-2">
                <input
                  value={proposalId} onChange={(e) => setProposalId(e.target.value)}
                  placeholder="Proposal ID"
                  className="flex-1 bg-[rgba(255,255,255,0.05)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-1)] outline-none focus:border-[var(--accent)]"
                />
                <button onClick={handleLoadProposal} disabled={loading} className="px-3 py-2 bg-[rgba(255,255,255,0.1)] text-[var(--text-1)] text-xs rounded-lg border border-[var(--border)] hover:bg-[rgba(255,255,255,0.15)] disabled:opacity-50">
                  Load
                </button>
              </div>
            </div>
          </>
        )}

        {/* Proposal details */}
        {proposal && (
          <>
            <div className="bg-[rgba(255,255,255,0.03)] rounded-xl p-4 border border-[var(--border-soft)]">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono text-[var(--text-3)]">{proposal.id.slice(0, 8)}...</span>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ color: STATUS_COLORS[proposal.status] || '#fff', background: `${STATUS_COLORS[proposal.status] || '#fff'}20` }}>
                  {proposal.status}
                </span>
              </div>
              <div className="space-y-1.5 text-xs text-[var(--text-2)]">
                <div>Source: <span className="font-mono text-[var(--text-3)]">{proposal.source_galaxy_id.slice(0, 12)}...</span></div>
                <div>Target: <span className="font-mono text-[var(--text-3)]">{proposal.target_galaxy_id.slice(0, 12)}...</span></div>
                <div>Entities matched: <span className="text-[var(--text-1)]">{proposal.entity_mappings_count}</span></div>
                <div>Bridges created: <span className="text-[var(--text-1)]">{proposal.bridges_created}</span></div>
              </div>
            </div>

            {/* Actions based on status */}
            {proposal.status === 'proposed' && (
              <div className="flex gap-2">
                <button onClick={handleAccept} disabled={loading} className="flex-1 px-3 py-2.5 bg-[#10B981] text-white text-xs font-medium rounded-lg hover:opacity-90 disabled:opacity-50">
                  Accept Merge
                </button>
                <button onClick={handleReject} disabled={loading} className="flex-1 px-3 py-2.5 bg-[rgba(239,68,68,0.2)] text-red-400 text-xs font-medium rounded-lg border border-[rgba(239,68,68,0.3)] hover:bg-[rgba(239,68,68,0.3)] disabled:opacity-50">
                  Reject
                </button>
              </div>
            )}

            {['accepted', 'sun_negotiation', 'entity_reconciliation', 'bridging'].includes(proposal.status) && (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <button onClick={handlePreviewSun} disabled={loading} className="flex-1 px-3 py-2 bg-[rgba(255,255,255,0.05)] text-[var(--text-1)] text-xs rounded-lg border border-[var(--border)] hover:bg-[rgba(255,255,255,0.1)] disabled:opacity-50">
                    Preview Sun
                  </button>
                  <button onClick={handlePreviewEntities} disabled={loading} className="flex-1 px-3 py-2 bg-[rgba(255,255,255,0.05)] text-[var(--text-1)] text-xs rounded-lg border border-[var(--border)] hover:bg-[rgba(255,255,255,0.1)] disabled:opacity-50">
                    Preview Entities
                  </button>
                </div>
                <button onClick={handleExecute} disabled={loading} className="w-full px-3 py-2.5 bg-[var(--accent)] text-white text-xs font-medium rounded-lg hover:opacity-90 disabled:opacity-50">
                  {loading ? 'Executing...' : 'Execute Merge'}
                </button>
              </div>
            )}

            {/* Sun preview */}
            {sunPreview && (
              <div className="bg-[rgba(255,255,255,0.03)] rounded-xl p-4 border border-[var(--border-soft)]">
                <div className="text-xs font-medium text-[var(--text-2)] mb-2">Merged Sun Preview</div>
                {Object.entries(sunPreview).map(([key, val]) => (
                  <div key={key} className="mb-2">
                    <div className="text-xs font-medium text-[var(--accent)]">{key}</div>
                    <pre className="text-xs text-[var(--text-3)] mt-0.5 overflow-x-auto max-h-24 overflow-y-auto">{JSON.stringify(val, null, 2)}</pre>
                  </div>
                ))}
              </div>
            )}

            {/* Entity mappings */}
            {entityMappings && (
              <div className="bg-[rgba(255,255,255,0.03)] rounded-xl p-4 border border-[var(--border-soft)]">
                <div className="text-xs font-medium text-[var(--text-2)] mb-2">Entity Reconciliation ({entityMappings.length} matches)</div>
                {entityMappings.length === 0 && <div className="text-xs text-[var(--text-3)]">No duplicate entities found.</div>}
                {entityMappings.map((m: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 py-1.5 border-b border-[var(--border-soft)] last:border-0 text-xs">
                    <span className="text-[var(--text-1)]">{m.source?.name}</span>
                    <span className="text-[var(--text-3)]">→</span>
                    <span className="text-[var(--text-1)]">{m.target?.name}</span>
                    <span className="ml-auto text-[var(--text-3)]">{m.match_type}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Execution result */}
            {result && (
              <div className="bg-[rgba(16,185,129,0.1)] rounded-xl p-4 border border-[rgba(16,185,129,0.3)]">
                <div className="text-xs font-medium text-[#10B981] mb-2">Merge Complete</div>
                <div className="space-y-1 text-xs text-[var(--text-2)]">
                  <div>Entities merged: {result.entities_merged}</div>
                  <div>Bridges created: {result.bridges_created}</div>
                  <div>Sun negotiated: {result.sun_negotiated ? 'Yes' : 'No'}</div>
                </div>
              </div>
            )}

            {/* Reset */}
            <button onClick={() => { setProposal(null); setProposalId(''); setSunPreview(null); setEntityMappings(null); setResult(null); }} className="text-xs text-[var(--text-3)] hover:text-[var(--text-2)]">
              ← Back to new proposal
            </button>
          </>
        )}

        {/* Error */}
        {error && (
          <div className="px-4 py-3 bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.3)] rounded-xl text-xs text-red-400">
            {error}
          </div>
        )}
      </div>
    </Panel>
  );
}
