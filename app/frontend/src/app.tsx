import { route } from './state/signals';
import { TopBar } from './components/TopBar';
import { NoticeToast } from './components/NoticeToast';
import { DashboardPage } from './pages/DashboardPage';
import { DiscoveryPage } from './pages/DiscoveryPage';

export function App() {
  return (
    <div class="app">
      <TopBar />
      <NoticeToast />
      <section class="page active" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {route.value === '/' ? <DashboardPage /> : <DiscoveryPage />}
      </section>
    </div>
  );
}
