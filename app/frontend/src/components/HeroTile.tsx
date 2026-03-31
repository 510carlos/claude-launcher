import { workspaces, activeCount, appName, installPrompt } from '../state/signals';

function InstallButton() {
  const prompt = installPrompt.value;
  if (!prompt) return null;

  const handleInstall = async () => {
    const p = prompt as any;
    p.prompt();
    const result = await p.userChoice;
    if (result.outcome === 'accepted') {
      installPrompt.value = null;
    }
  };

  return (
    <button class="btn btn-sm btn-ghost" onClick={handleInstall}
      style={{ gap: '5px', color: 'var(--muted)', fontSize: '12px' }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      Install
    </button>
  );
}

export function HeroTile() {
  const count = activeCount.value;
  const total = workspaces.value.length;
  const isActive = count > 0;

  // SVG ring: circumference = 2 * PI * 16 ≈ 100.5, we use dasharray 100
  // Full = offset 0, empty = offset 100
  const offset = isActive ? Math.max(100 - count * 30, 10) : 100;

  return (
    <div class={`glass-panel hero-tile`}>
      <div class="hero-title">
        <h1>{appName.value}</h1>
        <p>
          {total} workspace{total !== 1 ? 's' : ''}
          <InstallButton />
        </p>
      </div>
      <div class={`status-ring${isActive ? ' active' : ''}`}>
        <svg viewBox="0 0 36 36">
          <circle class="ring-bg" cx="18" cy="18" r="16" />
          <circle class="ring-fill" cx="18" cy="18" r="16"
            stroke-dashoffset={offset} />
        </svg>
        <span class="ring-count">{count}</span>
        <span class="ring-label">active</span>
      </div>
    </div>
  );
}
