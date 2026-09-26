import { useEffect, useRef, useState } from 'react';
import { contextLink } from './navigation';

type Progress = { dismissed: boolean; completed: number[] };
const key = 'gm-first-steps';
let memory: Progress | undefined;
const read = (): Progress => {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? '{}');
    return { dismissed: value.dismissed === true, completed: Array.isArray(value.completed) ? value.completed.filter((n: unknown) => n === 1 || n === 2 || n === 3) : [] };
  } catch { return memory ?? { dismissed: false, completed: [] }; }
};
function save(value: Progress) {
  memory = value;
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Usable for this session without storage. */ }
  window.dispatchEvent(new Event('gm-first-steps'));
}
/** Call only after the real action succeeds: replay played, changed controls rerun, or order filled. */
export function completeFirstStep(step: 1 | 2 | 3) {
  const value = read();
  if (!value.completed.includes(step)) save({ ...value, completed: [...value.completed, step] });
}
export function openFirstSteps() { save({ ...read(), dismissed: false }); }
export const firstStepLinks = () => [contextLink('#/replay', { day: '2026-08-26' }), contextLink('#/replay', { day: '2026-08-26', step: '2' }), contextLink('#/sandbox')];
const names = ['See the real day', 'Change the outcome', 'Place a first order'];

export default function FirstSteps() {
  const [progress, setProgress] = useState(read);
  const heading = useRef<HTMLHeadingElement>(null);
  const opening = new URLSearchParams(window.location.hash.split('?')[1]).get('start') === '1';
  useEffect(() => {
    memory = progress;
    const update = () => setProgress(memory ?? read());
    window.addEventListener('gm-first-steps', update);
    return () => window.removeEventListener('gm-first-steps', update);
  }, []);
  useEffect(() => { if (opening) { openFirstSteps(); heading.current?.focus(); } }, [opening]);
  if (progress.dismissed && !opening) return null;
  return <section className="first-steps" aria-labelledby="first-steps-title">
    <div className="first-steps-heading"><h2 id="first-steps-title" ref={heading} tabIndex={-1}>Your first 3 minutes</h2><button className="motion-toggle" onClick={() => { save({ ...progress, dismissed: true }); if (opening) window.location.hash = contextLink('#/'); }}>Dismiss checklist</button></div>
    <ol>{names.map((name, i) => <li key={name}><span className="step-state">{progress.completed.includes(i + 1) ? 'Complete' : `${i + 1}`}</span><a href={firstStepLinks()[i]}>{name}</a></li>)}</ol>
  </section>;
}

export function StepBanner({ step }: { step: 1 | 2 | 3 }) {
  return <aside className="step-banner" aria-label="First steps">Step {step} of 3 · <a href={step < 3 ? firstStepLinks()[step] : contextLink('#/tour')}>Next: {step < 3 ? names[step] : 'Review your progress'}</a></aside>;
}
