import { route } from './state/signals';
import { HeroTile } from './components/HeroTile';
import { BottomNav } from './components/BottomNav';
import { NoticeToast } from './components/NoticeToast';
import { DashboardPage } from './pages/DashboardPage';
import { DiscoveryPage } from './pages/DiscoveryPage';
import { UpdatesPage } from './pages/UpdatesPage';

function CurrentPage() {
  switch (route.value) {
    case '/discover': return <DiscoveryPage />;
    case '/updates': return <UpdatesPage />;
    default: return <DashboardPage />;
  }
}

export function App() {
  return (
    <div class="app">
      <div class="orb orb-top-right" />
      <div class="orb orb-bottom-left" />
      <HeroTile />
      <NoticeToast />
      <section class="page active" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <CurrentPage />
      </section>
      <BottomNav />
    </div>
  );
}
