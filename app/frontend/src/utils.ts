export function fmtTime(v: string | null | undefined): string {
  if (!v) return '\u2014';
  const d = new Date(v);
  if (isNaN(d.getTime())) return String(v);
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  return d.toLocaleDateString();
}

export function sessionIdentity(workspot: string, branch: string | null): string {
  return branch ? `${workspot} / ${branch}` : workspot;
}

const _adj = ['swift', 'bold', 'calm', 'keen', 'warm', 'cool', 'bright', 'sharp', 'quick', 'fresh', 'neat', 'wise', 'glad', 'fair', 'prime'];
const _noun = ['fix', 'patch', 'review', 'draft', 'spike', 'task', 'build', 'scan', 'check', 'tweak', 'pass', 'sync', 'push', 'test', 'ship'];

export function randomLabel(): string {
  return _adj[Math.random() * _adj.length | 0] + '-' + _noun[Math.random() * _noun.length | 0];
}

export function randomBranch(): string {
  return 'wt/' + randomLabel();
}
