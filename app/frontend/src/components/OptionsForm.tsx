import { useState } from 'preact/hooks';
import { randomLabel, randomBranch } from '../utils';

interface Props {
  onStart: (label: string, branch: string | null, worktree: boolean) => void;
  onCancel: () => void;
}

export function OptionsForm({ onStart, onCancel }: Props) {
  const [label, setLabel] = useState(randomLabel());
  const [branch, setBranch] = useState('');
  const [worktree, setWorktree] = useState(false);

  function handleWorktreeToggle(checked: boolean) {
    setWorktree(checked);
    setBranch(checked ? randomBranch() : '');
  }

  function handleStart() {
    onStart(label.trim() || randomLabel(), branch.trim() || null, worktree);
  }

  return (
    <div class="form-area open">
      <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>Session options</div>
      <div class="form-grid">
        <label class="form-label">
          Label
          <input
            class="form-input" type="text" placeholder="review, docs..."
            value={label} onInput={e => setLabel((e.target as HTMLInputElement).value)}
          />
        </label>
        <label class="form-label">
          Branch
          <input
            class="form-input" type="text" placeholder="feature/..."
            value={branch} onInput={e => setBranch((e.target as HTMLInputElement).value)}
          />
        </label>
      </div>
      <label class="form-label" style={{ flexDirection: 'row', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
        <input
          type="checkbox" checked={worktree}
          style={{ width: '20px', height: '20px', minHeight: 'auto', accentColor: 'var(--accent)' }}
          onChange={e => handleWorktreeToggle((e.target as HTMLInputElement).checked)}
        />
        <span>Use worktree <span style={{ color: 'var(--muted)', fontWeight: 400 }}>(isolated copy off main)</span></span>
      </label>
      <div class="actions">
        <button class="btn btn-primary btn-sm" onClick={handleStart}>Start with options</button>
        <button class="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
