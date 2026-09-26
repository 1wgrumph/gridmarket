import { useEffect, useState } from 'react';
import Shell from './components/Shell';
import Overview from './pages/Overview';
import Market from './pages/Market';
import Predictions from './pages/Predictions';
import Providers from './pages/Providers';
import Bots from './pages/Bots';
import BotProfile from './pages/BotProfile';
import Sandbox from './pages/Sandbox';
import Spec from './pages/Spec';
import Replay from './pages/Replay';

export const routes = ['#/', '#/market', '#/predictions', '#/providers', '#/bots', '#/bots/:id', '#/sandbox', '#/spec', '#/replay'] as const;

export default function App() {
  const [route, setRoute] = useState(window.location.hash || '#/');
  useEffect(() => {
    const update = () => setRoute(window.location.hash || '#/');
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  const path = route.split('?')[0];
  const page = path.startsWith('#/bots/') ? <BotProfile id={decodeURIComponent(path.slice('#/bots/'.length))} /> : ({
    '#/': <Overview />, '#/market': <Market />, '#/predictions': <Predictions />,
    '#/providers': <Providers />, '#/bots': <Bots />, '#/sandbox': <Sandbox />, '#/spec': <Spec />,
    '#/replay': <Replay />,
  } as Record<string, React.ReactNode>)[path] ?? <p>Page not found.</p>;
  return <Shell>{page}</Shell>;
}
