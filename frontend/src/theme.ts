export const theme = {
  colors: {
    bg: '#07041A',
    sun: '#F59E0B',
    sunGlow: '#FCD34D',
    sunHighlight: '#FEF3C7',
    violet700: '#7C3AED',
    violet300: '#A78BFA',
    teal500: '#0EA5E9',
    teal400: '#38BDF8',
    nebula: '#2D1B69',
    text1: '#F3F0FF',
    text2: '#C4B5FD',
    text3: '#9484C2',
    planetDefault: '#A78BFA',
    planets: {
      engineering: '#7C3AED',
      personal: '#0EA5E9',
      research: '#10B981',
      'side projects': '#A78BFA',
    } as Record<string, string>,
    lifecycle: {
      SEED: '#22D3EE',
      ACTIVE: '#7C3AED',
      MATURE: '#4F46E5',
      DORMANT: '#4B5563',
      ARCHIVED: '#374151',
    } as Record<string, string>,
    region: {
      analytical: '#7C3AED',
      procedural: '#0EA5E9',
      contextual: '#10B981',
    } as Record<string, string>,
    entity: {
      person: '#EC4899',
      org: '#F97316',
      tool: '#14B8A6',
      concept: '#8B5CF6',
      decision: '#F59E0B',
      code: '#6EE7B7',
    } as Record<string, string>,
  },
  animation: {
    orbitSpeed: 0.00018,
    pulseSpeed: 2000,
    starCount: 180,
  },
} as const;

/** Convert hex (#rrggbb) to rgba string */
export function hexA(hex: string, a: number): string {
  let h = hex.replace('#', '');
  if (h.length === 3) h = h.split('').map(c => c + c).join('');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}
