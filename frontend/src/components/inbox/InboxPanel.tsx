import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { InboxRow } from './InboxRow';
import { apiClient } from '../../api/client';
import { useGalaxy } from '../../api/galaxy';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface InboxPanelProps {
  galaxyId: string;
  onClose: () => void;
}

export function InboxPanel({ galaxyId, onClose }: InboxPanelProps) {
  const qc = useQueryClient();
  const trapRef = useFocusTrap<HTMLDivElement>(true);
  const { data: galaxy } = useGalaxy();
  const planetNames: string[] = (galaxy?.planets ?? []).map((p: any) => p.name);
  const { data: records, isLoading } = useQuery({
    queryKey: ['inbox', galaxyId],
    queryFn: () => apiClient.get(`/api/v1/routing/inbox?galaxy_id=${galaxyId}`).then(r => r.data),
    refetchInterval: 30000,
  });

  const routeMutation = useMutation({
    mutationFn: ({ stardustId, planetName, biomeName }: { stardustId: string; planetName: string; biomeName?: string }) =>
      apiClient.post(`/api/v1/routing/inbox/${stardustId}/route?planet_name=${encodeURIComponent(planetName)}${biomeName ? `&biome_name=${encodeURIComponent(biomeName)}` : ''}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inbox', galaxyId] }),
  });

  return (
    <div ref={trapRef} className="fixed right-0 top-0 h-full w-96 bg-[rgba(7,4,26,0.95)] border-l border-[rgba(196,181,253,0.2)] z-50 flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-[rgba(196,181,253,0.15)]">
        <div>
          <h2 className="text-sm font-semibold text-[#F3F0FF]">Inbox</h2>
          <p className="text-xs text-[#9484C2] mt-0.5">{records?.length ?? 0} records awaiting routing</p>
        </div>
        <button onClick={onClose} className="text-[#9484C2] hover:text-[#C4B5FD] text-sm" aria-label="Close">×</button>
      </div>
      <div className="px-4 py-3 bg-[rgba(124,58,237,0.08)] border-b border-[rgba(196,181,253,0.1)]">
        <p className="text-xs text-[#9484C2] leading-relaxed">
          These records could not be confidently routed to a Planet. Review each one and route it manually, or accept the suggestion.
        </p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {isLoading && <div className="p-4 text-xs text-[#9484C2]">Loading...</div>}
        {records?.length === 0 && (
          <div className="p-6 text-center">
            <div className="text-2xl mb-2">*</div>
            <p className="text-xs text-[#9484C2]">Inbox is clear. All knowledge has been routed.</p>
          </div>
        )}
        {records?.map((rec: any) => (
          <InboxRow key={rec.stardust.id} record={rec} planetNames={planetNames} routing={routeMutation.isPending}
            onRoute={(planetName, biomeName) => routeMutation.mutate({ stardustId: rec.stardust.id, planetName, biomeName })} />
        ))}
      </div>
    </div>
  );
}
