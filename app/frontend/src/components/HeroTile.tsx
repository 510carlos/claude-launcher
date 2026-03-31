import { workspaces, activeCount, appName } from '../state/signals';

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
        <p>{total} workspace{total !== 1 ? 's' : ''}</p>
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
