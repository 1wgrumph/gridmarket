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
import Replay from './pages/Replay';

export const routes = ['#/', '#/tour', '#/replay', '#/market', '#/predictions', '#/providers', '#/bots', '#/bots/:id', '#/sandbox', '#/spec'] as const;

function ReplayRoute() {
  const step = new URLSearchParams(window.location.hash.split('?')[1]).get('step');
  return <>
    <StepBanner step={step === '2' ? 2 : 1}/>
    <Replay />
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
    '#/': <Overview />, '#/tour': <Overview />, '#/replay': <ReplayRoute />, '#/market': <Market />, '#/predictions': <Predictions />,
    '#/providers': <Providers />, '#/bots': <Bots />, '#/sandbox': <Sandbox />, '#/spec': <Spec />,
  } as Record<string, React.ReactNode>)[path] ?? <><PageHeading eyebrow="PAGE UNAVAILABLE" title="Page not found"/><a href="#/">Return to Overview</a></>;
  return <Shell>{page}</Shell>;
}
