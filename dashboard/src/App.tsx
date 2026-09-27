import { useEffect, useState } from 'react';
import Shell from './components/Shell';
import Overview from './pages/Overview';
import Market, { PageHeading } from './pages/Market';
import Predictions from './pages/Predictions';
import Providers from './pages/Providers';
import Bots from './pages/Bots';
import BotProfile from './pages/BotProfile';
import Sandbox from './pages/Sandbox';
import Spec from './pages/Spec';
import { openFirstSteps, StepBanner } from './components/FirstSteps';
import { contextLink } from './components/navigation';

export const routes = ['#/', '#/tour', '#/replay', '#/market', '#/predictions', '#/providers', '#/bots', '#/bots/:id', '#/sandbox', '#/spec'] as const;

/** The replay page (C5) joins at the stretch assembly; until then its route says so. */
function ReplayPending() {
  return <>
    <PageHeading eyebrow="03 / REPLAY A REAL DAY" title="Replay"/><StepBanner step={new URLSearchParams(window.location.hash.split('?')[1]).get('step') === '2' ? 2 : 1}/>
    <section className="panel pending-page" aria-label="Replay status">
      <p role="status">Replay arrives with the full build.</p>
      <p>It replays one real Texas grid day with simulated home batteries. Meanwhile, <a href={contextLink('#/tour')}>open your checklist</a> or <a href={contextLink('#/market')}>watch the live market</a>.</p>
    </section>
  </>;
}

export default function App() {
  const [route, setRoute] = useState(window.location.hash || '#/');
  useEffect(() => {
    const update = () => setRoute(window.location.hash || '#/');
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  const path = route.split('?')[0] || '#/';
  useEffect(() => {
    if (path === '#/tour') { openFirstSteps(); window.location.replace(contextLink('#/', { start: '1' })); return; }
    const names: Record<string, string> = { '#/': 'Overview', '#/replay': 'Replay', '#/market': 'Market', '#/predictions': 'Predictions', '#/providers': 'Providers', '#/bots': 'Bots', '#/sandbox': 'Judge sandbox', '#/spec': 'Specification' };
    const params = new URLSearchParams(route.split('?')[1]);
    const context: string[] = []; params.forEach((value, key) => context.push(`${key}: ${value}`));
    document.title = [path.startsWith('#/bots/') ? `Bot profile · ${decodeURIComponent(path.slice('#/bots/'.length))}` : names[path] ?? 'Page not found', ...context, 'GridMarket'].join(' – ');
  }, [route, path]);
  const page = path.startsWith('#/bots/') ? <BotProfile id={decodeURIComponent(path.slice('#/bots/'.length))} /> : ({
    '#/': <Overview />, '#/tour': <Overview />, '#/replay': <ReplayPending />, '#/market': <Market />, '#/predictions': <Predictions />,
    '#/providers': <Providers />, '#/bots': <Bots />, '#/sandbox': <Sandbox />, '#/spec': <Spec />,
  } as Record<string, React.ReactNode>)[path] ?? <><PageHeading eyebrow="PAGE UNAVAILABLE" title="Page not found"/><a href="#/">Return to Overview</a></>;
  return <Shell>{page}</Shell>;
}
