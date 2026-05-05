import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { useQueryClient } from '@tanstack/react-query';
import { Button, OrionMark } from '../components/ui';

const ROLES = [
  { value: 'developer', name: 'Developer', desc: 'Code, architecture, decisions, and tooling.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg> },
  { value: 'designer', name: 'Designer', desc: 'Visual systems, components, brand artifacts.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="13.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="10.5" r="2.5"/><circle cx="8.5" cy="7.5" r="2.5"/><circle cx="6.5" cy="12.5" r="2.5"/><path d="M12 22a9 9 0 1 1 0-18 9 9 0 0 1 6.5 15.2 1.5 1.5 0 0 1-1.1.4H14a2 2 0 0 0-1.6 3.2A1 1 0 0 1 12 22z"/></svg> },
  { value: 'researcher', name: 'Researcher', desc: 'Papers, citations, hypotheses, lab notes.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg> },
  { value: 'founder', name: 'Founder · Operator', desc: 'Strategy, customers, hiring, decisions.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg> },
  { value: 'other', name: 'Other', desc: "We'll start with a neutral default Galaxy.", icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg> },
];

const SOURCES = [
  { value: 'folder', name: 'Local folder', desc: 'Markdown, code, notes — recursive.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg> },
  { value: 'obsidian', name: 'Obsidian vault', desc: 'Preserves links and tags as bridges.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 4 8v8l8 6 8-6V8z"/><path d="M12 22V12"/><path d="m4 8 8 4 8-4"/></svg> },
  { value: 'git', name: 'Git repository', desc: 'Reads README, ADRs, commit history.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M6 9v6a3 3 0 0 0 3 3h2"/><path d="M15 6h-2a3 3 0 0 0-3 3v6"/></svg> },
  { value: 'empty', name: 'Empty Galaxy', desc: 'Start blank. Agents fill it as you work.', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/></svg> },
];

const STORAGE_KEY = 'orion-onboarding-progress';

interface OnboardingState {
  step: number; role: string; source: string; importPath: string;
  biomeName: string; userName: string; goal: string; commStyle: string;
  tools: string[]; contradictionPref: string; steeringDocPath: string;
}

function loadProgress(): Partial<OnboardingState> {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch { return {}; }
}

function saveProgress(state: OnboardingState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function clearProgress() {
  localStorage.removeItem(STORAGE_KEY);
}

export default function OnboardingView() {
  const saved = loadProgress();
  const [step, setStep] = useState(saved.step || 1);
  const [role, setRole] = useState(saved.role || 'developer');
  const [source, setSource] = useState(saved.source || 'folder');
  const [importPath, setImportPath] = useState(saved.importPath || '');
  const [importWarning, setImportWarning] = useState('');
  const [biomeName, setBiomeName] = useState(saved.biomeName || 'Orion Backend');
  const [userName, setUserName] = useState(saved.userName || '');
  const [goal, setGoal] = useState(saved.goal || '');
  const [commStyle, setCommStyle] = useState(saved.commStyle || 'direct');
  const [tools, setTools] = useState<string[]>(saved.tools || []);
  const [toolInput, setToolInput] = useState('');
  const [contradictionPref, setContradictionPref] = useState(saved.contradictionPref || 'flag_and_ask');
  const [steeringDocPath, setSteeringDocPath] = useState(saved.steeringDocPath || '');
  const [steeringDocContent, setSteeringDocContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const nameRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();

  useEffect(() => {
    if (step === 3) setTimeout(() => nameRef.current?.focus(), 50);
  }, [step]);

  // Persist progress
  useEffect(() => {
    saveProgress({ step, role, source, importPath, biomeName, userName, goal, commStyle, tools, contradictionPref, steeringDocPath });
  }, [step, role, source, importPath, biomeName, userName, goal, commStyle, tools, contradictionPref, steeringDocPath]);

  useEffect(() => {
    if (source === 'obsidian' && !importPath) setImportPath('/vault');
    else if (source !== 'obsidian' && importPath === '/vault') setImportPath('');
  }, [source]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Enter') { if (step < 6) setStep(step + 1); else handleFinish(); }
      else if (e.key === 'ArrowLeft' && step > 1) setStep(step - 1);
      else if (e.key === 'ArrowRight' && step < 6) setStep(step + 1);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [step, role, source, biomeName, userName, goal, tools, commStyle, contradictionPref, steeringDocPath]);

  const handleFinish = async () => {
    if (loading) return;
    setLoading(true);
    setSubmitError('');
    try {
      const result = await apiClient.post<{ import_started: boolean }>('/api/v1/onboarding/start', {
        role: role === 'founder' ? 'Technical Founder' : role.charAt(0).toUpperCase() + role.slice(1),
        first_biome_name: biomeName || 'General',
        import_path: source !== 'empty' && importPath.trim() ? importPath.trim() : null,
        source_type: source,
        name: userName,
        goal,
        tools,
        communication_style: commStyle,
        contradiction_preference: contradictionPref,
        steering_doc_path: steeringDocPath.trim() || null,
        steering_doc_content: steeringDocContent,
      });
      qc.invalidateQueries({ queryKey: ['galaxy'] });
      if (source !== 'empty' && importPath.trim() && !result.import_started) {
        setImportWarning(`Vault import could not start — path "${importPath}" was not accessible from the server. Your Galaxy was created, but you can re-import later from Settings.`);
      }
      clearProgress();
      navigate('/');
    } catch (err: unknown) {
      console.error('Onboarding failed:', err);
      setSubmitError((err as Error)?.message ?? 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const slug = biomeName ? biomeName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') : 'untitled';
  const nameLen = biomeName.length;
  const nameValid = nameLen > 0 && nameLen <= 40;

  return (
    <div className="fixed inset-0 flex items-center justify-center">
      {/* Star backdrop */}
      <div className="absolute inset-0">
        <StarCanvas />
      </div>
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(ellipse 50% 60% at 88% 12%, rgba(245,158,11,0.10), transparent 55%), radial-gradient(ellipse 50% 50% at 12% 92%, rgba(124,58,237,0.10), transparent 60%)',
      }} />

      {/* Logo */}
      <div className="absolute top-7 right-8 z-[6]">
        <OrionMark />
      </div>

      {/* Step switcher */}
      <div className="absolute top-6 right-1/2 translate-x-1/2 flex gap-1.5 z-[6]">
        {[1, 2, 3, 4, 5, 6].map((s) => (
          <button
            key={s}
            onClick={() => setStep(s)}
            className={`px-3 py-1.5 rounded-full text-[11px] font-mono tracking-[0.04em] cursor-pointer border backdrop-blur-sm transition-all duration-150 ${step === s ? 'text-white bg-[var(--violet-700)] border-[var(--violet-700)]' : 'text-[var(--text-3)] bg-[rgba(7,4,26,0.6)] border-[var(--border-soft)] hover:text-[var(--text-1)]'}`}
          >
            Step {s}
          </button>
        ))}
      </div>

      {/* Card */}
      <div className="relative z-[1] w-[720px] bg-gradient-to-b from-[rgba(45,27,105,0.42)] to-[rgba(45,27,105,0.28)] border border-[var(--border)] rounded-[18px] px-16 pt-14 pb-12 shadow-[0_30px_80px_rgba(0,0,0,0.55),0_0_0_1px_rgba(124,58,237,0.08)_inset] backdrop-blur-[20px] animate-[rise_600ms_ease-expo]">
        {/* Step bar */}
        <div className="flex items-center gap-2 mb-7">
          <span className="font-mono text-[11px] text-[var(--text-3)] tracking-[0.08em] uppercase mr-3.5">Step {step} of 6</span>
          {[1, 2, 3, 4, 5, 6].map((s) => (
            <span key={s} className={`w-1.5 h-1.5 rounded-full transition-all duration-[250ms] ease-expo ${s === step ? 'bg-white shadow-[0_0_8px_rgba(255,255,255,0.4)]' : s < step ? 'bg-[var(--violet-300)]' : 'bg-[rgba(255,255,255,0.18)]'}`} />
          ))}
        </div>

        <div className="animate-[step-in_320ms_ease-expo]" key={step}>
          {step === 1 && (
            <>
              <h1 className="font-display text-[28px] font-semibold tracking-tight leading-tight mb-2">Let's set up your Galaxy.</h1>
              <p className="text-sm text-[var(--text-2)] leading-relaxed mb-8 max-w-[520px]">Orion runs locally on your machine and never leaves it. To organize your knowledge, we'll start with what you do most.</p>
              <div className="flex flex-col gap-2">
                {ROLES.map((r) => (
                  <label
                    key={r.value}
                    className={`grid grid-cols-[auto_1fr_auto] gap-3.5 items-center p-3.5 bg-[var(--surface-3)] border rounded-[10px] cursor-pointer transition-all duration-150 ${role === r.value ? 'border-[var(--violet-300)] bg-[rgba(124,58,237,0.16)]' : 'border-[var(--border-soft)] hover:border-[var(--border)] hover:bg-[var(--surface-2)]'}`}
                    onClick={() => setRole(r.value)}
                  >
                    <span className={`w-4 h-4 rounded-full border-[1.5px] flex items-center justify-center transition-all duration-150 ${role === r.value ? 'border-[var(--violet-300)]' : 'border-[var(--text-3)]'}`}>
                      {role === r.value && <span className="w-2 h-2 rounded-full bg-[var(--violet-300)] shadow-[0_0_6px_var(--violet-300)]" />}
                    </span>
                    <span className="flex flex-col">
                      <span className="text-[var(--text-1)] text-sm font-medium">{r.name}</span>
                      <span className="text-[var(--text-3)] text-xs mt-0.5">{r.desc}</span>
                    </span>
                    <span className="w-8 h-8 rounded-lg bg-[rgba(124,58,237,0.12)] border border-[var(--border-soft)] flex items-center justify-center text-[var(--violet-300)]">
                      <span className="w-4 h-4">{r.icon}</span>
                    </span>
                  </label>
                ))}
              </div>
              <div className="flex items-center justify-between mt-8">
                <span className="text-[11px] text-[var(--text-3)] cursor-pointer hover:text-[var(--text-2)]" onClick={() => setStep(2)}>Skip and decide later</span>
                <Button variant="primary" kbd="↵" onClick={() => setStep(2)}>Continue</Button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h1 className="font-display text-[28px] font-semibold tracking-tight leading-tight mb-2">Bring in what you already know.</h1>
              <p className="text-sm text-[var(--text-2)] leading-relaxed mb-8 max-w-[520px]">Pick one or skip — Orion will scan, extract entities, and seed your first Planets. Nothing leaves your machine.</p>
              <div className="grid grid-cols-2 gap-2.5">
                {SOURCES.map((s) => (
                  <label
                    key={s.value}
                    className={`p-4 bg-[var(--surface-3)] border rounded-[10px] cursor-pointer transition-all duration-150 grid grid-cols-[auto_1fr_auto] gap-3.5 items-center ${source === s.value ? 'border-[var(--violet-300)] bg-[rgba(124,58,237,0.16)]' : 'border-[var(--border-soft)] hover:border-[var(--border)] hover:bg-[var(--surface-2)]'}`}
                    onClick={() => setSource(s.value)}
                  >
                    <span className={`w-4 h-4 rounded-full border-[1.5px] flex items-center justify-center ${source === s.value ? 'border-[var(--violet-300)]' : 'border-[var(--text-3)]'}`}>
                      {source === s.value && <span className="w-2 h-2 rounded-full bg-[var(--violet-300)] shadow-[0_0_6px_var(--violet-300)]" />}
                    </span>
                    <span className="flex flex-col">
                      <span className="text-[var(--text-1)] text-sm font-medium">{s.name}</span>
                      <span className="text-[var(--text-3)] text-xs mt-0.5">{s.desc}</span>
                    </span>
                    <span className="w-9 h-9 rounded-lg bg-[rgba(124,58,237,0.12)] border border-[var(--border-soft)] flex items-center justify-center text-[var(--violet-300)]">
                      <span className="w-[18px] h-[18px]">{s.icon}</span>
                    </span>
                  </label>
                ))}
              </div>
              {source !== 'empty' && (
                <div className="mt-4">
                  <div className="flex gap-2">
                    <input
                      value={importPath}
                      onChange={(e) => setImportPath(e.target.value)}
                      placeholder={source === 'obsidian' ? '/vault' : source === 'git' ? '~/projects/my-repo' : '~/Documents/notes'}
                      className="flex-1 h-10 px-3.5 bg-[var(--surface-3)] border border-[var(--border-soft)] rounded-lg text-sm text-[var(--text-1)] placeholder:text-[var(--text-3)] outline-none focus:border-[var(--violet-300)] transition-colors duration-150"
                    />
                    <label className="h-10 px-3.5 flex items-center gap-1.5 bg-[var(--surface-3)] border border-[var(--border-soft)] rounded-lg text-sm text-[var(--text-2)] cursor-pointer hover:border-[var(--violet-300)] hover:text-[var(--text-1)] transition-colors">
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 4.5A1.5 1.5 0 013.5 3h3.172a1.5 1.5 0 011.06.44l.768.767a1.5 1.5 0 001.06.439H12.5A1.5 1.5 0 0114 6.146V11.5a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 012 11.5v-7z" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      Browse
                      <input type="file" className="hidden" {...{ webkitdirectory: '', directory: '' } as any} onChange={(e) => {
                        const files = e.target.files;
                        if (files && files.length > 0) {
                          const path = files[0].webkitRelativePath.split('/')[0];
                          setImportPath(path);
                        }
                      }} />
                    </label>
                  </div>
                  {source === 'obsidian' && (
                    <p className="mt-1.5 text-[11px] text-[var(--text-3)]">Your vault is mounted at <code className="font-mono text-[var(--text-2)]">/vault</code> inside Orion's Docker container.</p>
                  )}
                </div>
              )}
              <div className="flex items-center justify-between mt-8">
                <span className="inline-flex items-center gap-1.5 text-xs text-[var(--text-3)]">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#34D399" strokeWidth="2"><path d="M20 6 9 17l-5-5"/></svg>
                  <span className="text-[#34D399]">Local-only</span> · indexes never leave this machine
                </span>
                <div className="flex gap-2.5">
                  <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
                  <Button variant="primary" kbd="↵" onClick={() => setStep(3)}>Continue</Button>
                </div>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h1 className="font-display text-[28px] font-semibold tracking-tight leading-tight mb-2">Name your first Biome.</h1>
              <p className="text-sm text-[var(--text-2)] leading-relaxed mb-8 max-w-[520px]">A Biome is a single project's living memory. You'll see it grow as you and your agents add to it.</p>

              <input
                ref={nameRef}
                value={biomeName}
                onChange={(e) => setBiomeName(e.target.value)}
                maxLength={40}
                placeholder="e.g. Orion Backend"
                className="w-full h-14 px-[18px] bg-[rgba(0,0,0,0.25)] border border-[var(--border)] rounded-xl text-[var(--text-1)] font-display text-[22px] font-medium tracking-tight outline-none transition-all duration-200 placeholder:text-[var(--text-3)] placeholder:font-normal focus:border-[var(--violet-300)] focus:bg-[rgba(124,58,237,0.10)] focus:shadow-[0_0_0_4px_rgba(124,58,237,0.10)]"
              />
              <div className="flex justify-between items-center mt-2 text-[11px] font-mono text-[var(--text-3)]">
                <span>{nameLen}/40 · letters, numbers, spaces</span>
                <span className={nameValid ? 'text-[#34D399]' : 'text-[var(--warning)]'}>{nameValid ? 'valid' : nameLen === 0 ? 'enter a name' : 'too long'}</span>
              </div>

              {/* Live biome preview */}
              <div className="mt-7 p-8 border border-[var(--border-soft)] rounded-[14px] grid grid-cols-[120px_1fr] gap-7 items-center relative overflow-hidden" style={{ background: 'radial-gradient(ellipse 60% 60% at 50% 50%, rgba(34,211,238,0.08), transparent 70%), rgba(0,0,0,0.25)' }}>
                {/* Seed circle */}
                <div className="w-24 h-24 relative flex items-center justify-center">
                  <div className="absolute -inset-5 rounded-full animate-[seed-breathe_3.6s_ease-in-out_infinite]" style={{ background: 'radial-gradient(circle, rgba(34,211,238,0.45), transparent 65%)' }} />
                  <div className="w-16 h-16 rounded-full relative" style={{
                    background: 'radial-gradient(circle at 35% 32%, #67E8F9, #22D3EE 55%, #0891B2)',
                    boxShadow: '0 0 30px rgba(34,211,238,0.45), inset -8px -10px 20px rgba(0,0,0,0.4)',
                  }}>
                    <div className="absolute top-[14%] left-[26%] w-[22%] h-[18%] rounded-full bg-[rgba(255,255,255,0.5)] blur-[2px]" />
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <div className="font-display text-[22px] font-medium text-[var(--text-1)] tracking-tight leading-tight">
                    {biomeName || 'Untitled Biome'}
                    <span className="inline-block w-px h-[22px] bg-[var(--violet-300)] ml-0.5 align-[-3px] animate-[blink_1s_steps(2)_infinite]" />
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <span className="inline-flex items-center gap-1.5 text-[10px] font-medium tracking-[0.08em] uppercase px-2 py-[3px] rounded-full border border-[var(--border-soft)] text-[var(--text-2)]">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--seed)] shadow-[0_0_6px_var(--seed)]" />
                      Seed
                    </span>
                    <span className="text-[var(--text-3)] font-mono text-[11px] px-2 py-[3px] rounded-full border border-[var(--border-soft)]">
                      Engineering / {slug || 'untitled'}
                    </span>
                    <span className="text-[10px] font-medium tracking-[0.08em] uppercase px-2 py-[3px] rounded-full border border-[var(--border-soft)] text-[var(--text-2)]">
                      0 stardust
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-3)] leading-relaxed max-w-[420px] mt-1">
                    {biomeName
                      ? `Starting "${biomeName}" as a Seed Biome under Engineering. As soon as you connect an agent, it will begin accumulating stardust.`
                      : 'Starting from an empty seed. As soon as you connect an agent, this Biome will begin accumulating stardust.'}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between mt-8">
                <span className="text-[11px] text-[var(--text-3)] cursor-pointer hover:text-[var(--text-2)]" onClick={() => setStep(4)}>Use a default name</span>
                <div className="flex gap-2.5">
                  <Button variant="ghost" onClick={() => setStep(2)}>Back</Button>
                  <Button variant="primary" kbd="↵" onClick={() => setStep(4)}>Continue</Button>
                </div>
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <h1 className="font-display text-[28px] font-semibold tracking-tight leading-tight mb-2">Tell Orion about you.</h1>
              <p className="text-sm text-[var(--text-2)] leading-relaxed mb-8 max-w-[520px]">Your name and current focus help agents personalize their responses from the start.</p>

              <div className="flex flex-col gap-4">
                <div>
                  <label className="text-xs text-[var(--text-3)] uppercase tracking-[0.08em] mb-1.5 block">Your name</label>
                  <input value={userName} onChange={(e) => setUserName(e.target.value)} placeholder="e.g. Andy" className="w-full h-11 px-4 bg-[rgba(0,0,0,0.25)] border border-[var(--border)] rounded-lg text-[var(--text-1)] text-sm outline-none focus:border-[var(--violet-300)]" />
                </div>
                <div>
                  <label className="text-xs text-[var(--text-3)] uppercase tracking-[0.08em] mb-1.5 block">What are you working on?</label>
                  <input value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="e.g. Building a personal AI knowledge system" className="w-full h-11 px-4 bg-[rgba(0,0,0,0.25)] border border-[var(--border)] rounded-lg text-[var(--text-1)] text-sm outline-none focus:border-[var(--violet-300)]" />
                </div>
                <div>
                  <label className="text-xs text-[var(--text-3)] uppercase tracking-[0.08em] mb-1.5 block">Communication style</label>
                  <div className="flex gap-2">
                    {(['direct', 'thorough', 'socratic'] as const).map((s) => (
                      <button key={s} onClick={() => setCommStyle(s)} className={`flex-1 py-2.5 rounded-lg text-sm border transition-all ${commStyle === s ? 'text-white bg-[var(--violet-700)] border-[var(--violet-700)]' : 'text-[var(--text-3)] bg-[var(--surface-3)] border-[var(--border-soft)] hover:text-[var(--text-1)]'}`}>
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between mt-8">
                <span className="text-[11px] text-[var(--text-3)] cursor-pointer hover:text-[var(--text-2)]" onClick={() => setStep(5)}>Skip</span>
                <div className="flex gap-2.5">
                  <Button variant="ghost" onClick={() => setStep(3)}>Back</Button>
                  <Button variant="primary" kbd="↵" onClick={() => setStep(5)}>Continue</Button>
                </div>
              </div>
            </>
          )}

          {step === 5 && (
            <>
              <h1 className="font-display text-[28px] font-semibold tracking-tight leading-tight mb-2">Got a steering document?</h1>
              <p className="text-sm text-[var(--text-2)] leading-relaxed mb-8 max-w-[520px]">If you have a CLAUDE.md, .cursorrules, or any markdown file that defines how agents should behave — point Orion to it. It'll be stored in the Sun and always available to every agent.</p>

              <div className="flex flex-col gap-4">
                <div>
                  <label className="text-xs text-[var(--text-3)] uppercase tracking-[0.08em] mb-1.5 block">Path to steering document</label>
                  <div className="flex gap-2">
                    <input value={steeringDocPath} onChange={(e) => { setSteeringDocPath(e.target.value); setSteeringDocContent(null); }} placeholder="e.g. ~/projects/my-app/CLAUDE.md" className="flex-1 h-11 px-4 bg-[rgba(0,0,0,0.25)] border border-[var(--border)] rounded-lg text-[var(--text-1)] text-sm font-mono outline-none focus:border-[var(--violet-300)]" />
                    <label className="h-11 px-4 flex items-center gap-1.5 bg-[rgba(0,0,0,0.25)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-2)] cursor-pointer hover:border-[var(--violet-300)] hover:text-[var(--text-1)] transition-colors">
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 14h10M8 2v9m0 0L5 8m3 3l3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      Browse
                      <input type="file" accept=".md,.markdown,.txt" className="hidden" onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setSteeringDocPath(file.name);
                          file.text().then(setSteeringDocContent);
                        }
                      }} />
                    </label>
                  </div>
                  <p className="mt-1.5 text-[11px] text-[var(--text-3)]">The file will be read once and stored in your Galaxy. You can re-import it anytime from the Sun view.</p>
                </div>
              </div>

              <div className="flex items-center justify-between mt-8">
                <span className="text-[11px] text-[var(--text-3)] cursor-pointer hover:text-[var(--text-2)]" onClick={() => setStep(6)}>Skip — use default template</span>
                <div className="flex gap-2.5">
                  <Button variant="ghost" onClick={() => setStep(4)}>Back</Button>
                  <Button variant="primary" kbd="↵" onClick={() => setStep(6)}>Continue</Button>
                </div>
              </div>
            </>
          )}

          {step === 6 && (
            <>
              <h1 className="font-display text-[28px] font-semibold tracking-tight leading-tight mb-2">Your tools and preferences.</h1>
              <p className="text-sm text-[var(--text-2)] leading-relaxed mb-8 max-w-[520px]">These become entities in your Galaxy. Agents will know your stack from day one.</p>

              <div className="flex flex-col gap-4">
                <div>
                  <label className="text-xs text-[var(--text-3)] uppercase tracking-[0.08em] mb-1.5 block">Tools &amp; technologies</label>
                  <div className="flex gap-2 flex-wrap mb-2">
                    {tools.map((t) => (
                      <span key={t} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-[rgba(124,58,237,0.16)] border border-[var(--violet-300)] text-[var(--text-1)]">
                        {t}
                        <button onClick={() => setTools(tools.filter(x => x !== t))} className="text-[var(--text-3)] hover:text-white" aria-label="Remove">×</button>
                      </span>
                    ))}
                  </div>
                  <input value={toolInput} onChange={(e) => setToolInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && toolInput.trim()) { e.stopPropagation(); setTools([...tools, toolInput.trim()]); setToolInput(''); }}} placeholder="Type a tool and press Enter" className="w-full h-11 px-4 bg-[rgba(0,0,0,0.25)] border border-[var(--border)] rounded-lg text-[var(--text-1)] text-sm outline-none focus:border-[var(--violet-300)]" />
                </div>
                <div>
                  <label className="text-xs text-[var(--text-3)] uppercase tracking-[0.08em] mb-1.5 block">When agents find contradictions</label>
                  <div className="flex gap-2">
                    {([['flag_and_ask', 'Flag & ask me'], ['auto_resolve', 'Auto-resolve'], ['log_only', 'Log silently']] as const).map(([val, label]) => (
                      <button key={val} onClick={() => setContradictionPref(val)} className={`flex-1 py-2.5 rounded-lg text-sm border transition-all ${contradictionPref === val ? 'text-white bg-[var(--violet-700)] border-[var(--violet-700)]' : 'text-[var(--text-3)] bg-[var(--surface-3)] border-[var(--border-soft)] hover:text-[var(--text-1)]'}`}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {importWarning && (
                <div className="mt-4 p-3.5 rounded-lg border border-[var(--warning)] bg-[rgba(245,158,11,0.08)] text-xs text-[var(--warning)] leading-relaxed">
                  {importWarning}
                </div>
              )}
              {submitError && (
                <div className="mt-4 p-3.5 rounded-lg border border-red-500/40 bg-red-500/08 text-xs text-red-400 leading-relaxed">
                  {submitError}
                </div>
              )}
              <div className="flex items-center justify-between mt-8">
                <span className="text-[11px] text-[var(--text-3)] cursor-pointer hover:text-[var(--text-2)]" onClick={handleFinish}>Skip and finish</span>
                <div className="flex gap-2.5">
                  <Button variant="ghost" onClick={() => setStep(5)}>Back</Button>
                  <Button variant="primary" kbd="↵" onClick={handleFinish} disabled={loading}>
                    {loading ? 'Creating…' : 'Open my Galaxy'}
                  </Button>
                </div>
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
}

/** Lightweight star canvas for the onboarding backdrop */
function StarCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = canvasRef.current!;
    const ctx = cv.getContext('2d')!;
    const DPR = Math.min(devicePixelRatio || 1, 2);
    let stars: { x: number; y: number; r: number; a: number; phase: number; speed: number }[] = [];
    let W = 0, H = 0;

    function resize() {
      W = innerWidth; H = innerHeight;
      cv.width = W * DPR; cv.height = H * DPR;
      cv.style.width = W + 'px'; cv.style.height = H + 'px';
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      const N = Math.round((W * H) / 9000);
      stars = Array.from({ length: N }, () => ({
        x: Math.random() * W, y: Math.random() * H,
        r: 0.3 + Math.random() * 1.1, a: 0.1 + Math.random() * 0.6,
        phase: Math.random() * Math.PI * 2, speed: 0.5 + Math.random() * 1.5,
      }));
    }

    let animId: number;
    function draw(t: number) {
      ctx.clearRect(0, 0, W, H);
      for (const s of stars) {
        const alpha = s.a * (0.6 + 0.4 * Math.sin(t * 0.0006 * s.speed + s.phase));
        ctx.fillStyle = `rgba(243, 240, 255, ${alpha})`;
        ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2); ctx.fill();
      }
      animId = requestAnimationFrame(draw);
    }

    window.addEventListener('resize', resize);
    resize();
    animId = requestAnimationFrame(draw);
    return () => { window.removeEventListener('resize', resize); cancelAnimationFrame(animId); };
  }, []);

  return <canvas ref={canvasRef} className="w-full h-full block" />;
}
