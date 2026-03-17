import { pendingPhases } from '../state/signals';

interface Props {
  sessionId: string;
}

const steps = [
  { label: 'Connecting to workspace...', icon: '1' },
  { label: 'Starting Claude...', icon: '2' },
  { label: 'Generating URL...', icon: '3' },
];

export function ProgressSteps({ sessionId }: Props) {
  const p = pendingPhases.value[sessionId] || { phase: 0 };
  const phase = p.phase;
  const barWidth = phase === 0 ? 15 : phase === 1 ? 45 : 80;

  return (
    <div class="progress">
      {steps.map((s, i) => {
        const cls = i < phase ? 'done' : i === phase ? 'active' : '';
        const icon = i < phase ? '\u2713' : s.icon;
        return (
          <div key={i} class={`progress-step ${cls}`}>
            <span class="progress-step-icon">{icon}</span> {s.label}
          </div>
        );
      })}
      <div class="progress-bar">
        <div class="progress-bar-fill" style={{ width: `${barWidth}%` }} />
      </div>
      <div class="progress-time">Usually takes 10–20 seconds</div>
    </div>
  );
}
