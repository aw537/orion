import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './components/ui';
import GalaxyView from './views/GalaxyView';
import PlanetView from './views/PlanetView';
import BiomeView from './views/BiomeView';
import DetailView from './views/DetailView';
import DashboardView from './views/DashboardView';
import OnboardingView from './views/OnboardingView';
import SunView from './views/SunView';
import SettingsView from './views/SettingsView';
import KnowledgeGraphView from './views/KnowledgeGraphView';

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1 } } });

function ShellRoute({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<GalaxyView />} />
          <Route path="/planet/:planetId" element={<ShellRoute><PlanetView /></ShellRoute>} />
          <Route path="/biome/:biomeId" element={<ShellRoute><BiomeView /></ShellRoute>} />
          <Route path="/detail/:type/:id" element={<ShellRoute><DetailView /></ShellRoute>} />
          <Route path="/dashboard" element={<ShellRoute><DashboardView /></ShellRoute>} />
          <Route path="/onboarding" element={<OnboardingView />} />
          <Route path="/sun" element={<ShellRoute><SunView /></ShellRoute>} />
          <Route path="/settings" element={<ShellRoute><SettingsView /></ShellRoute>} />
          <Route path="/graph" element={<ShellRoute><KnowledgeGraphView /></ShellRoute>} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
