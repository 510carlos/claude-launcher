import { WorkspaceGrid } from '../components/WorkspaceGrid';
import { RecentSessions } from '../components/RecentSessions';

export function DashboardPage() {
  return (
    <>
      <WorkspaceGrid />
      <RecentSessions />
    </>
  );
}
