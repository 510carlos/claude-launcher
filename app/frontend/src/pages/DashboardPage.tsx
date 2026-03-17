import { ActiveSessions } from '../components/ActiveSessions';
import { WorkspaceGrid } from '../components/WorkspaceGrid';
import { RecentSessions } from '../components/RecentSessions';

export function DashboardPage() {
  return (
    <>
      <ActiveSessions />
      <WorkspaceGrid />
      <RecentSessions />
    </>
  );
}
