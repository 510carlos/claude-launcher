import { useState } from 'preact/hooks';
import type { Session } from '../types';
import { fmtTime, sessionIdentity } from '../utils';
import { ProgressSteps } from './ProgressSteps';
import { killSession as apiKill, deleteSession as apiDelete, getSessionOutput } from '../api/sessions';
import { sessions, clearPhaseTimer, showNotice } from '../state/signals';
import { refresh } from '../state/polling';

interface Props {
  session: Session;
  showKill?: boolean;
  showDelete?: boolean;
}

export function SessionCard({ session: s, showKill = false, showDelete = false }: Props) {
  const [outputOpen, setOutputOpen] = useState(false);
  const [outputText, setOutputText] = useState('');

  const identity = sessionIdentity(s.workspot, s.branch);
  const time = fmtTime(s.created_at);
  const isPending = s.status === 'pending';
  const isRunning = s.status === 'running';

  async function handleKill() {
    const found = sessions.value.find(x => x.id === s.id);
    if (found) found.status = 'stopped';
    sessions.value = [...sessions.value];
    clearPhaseTimer(s.id);
    showNotice('Stopped.');
    try {
      await apiKill(s.id);
      await refresh();
    } catch { showNotice('Failed to stop.', 'error'); await refresh(); }
  }

  async function handleDelete() {
    sessions.value = sessions.value.filter(x => x.id !== s.id);
    showNotice('Deleted.');
    try {
      await apiDelete(s.id);
    } catch { showNotice('Failed to delete.', 'error'); await refresh(); }
  }

  async function toggleOutput() {
    if (outputOpen) { setOutputOpen(false); return; }
    setOutputText('Loading...');
    setOutputOpen(true);
    try {
      const data = await getSessionOutput(s.id);
      setOutputText(data.output || '(no output yet)');
    } catch { setOutputText('Failed to load.'); }
  }

  return (
    <article class={`card ${s.status}`}>
      <div class="card-head">
        <div>
          <div class="card-title">{identity}</div>
          <div class="card-meta">
            {s.label ? `${s.label} \u00b7 ` : ''}{time}
            {!isRunning && !isPending ? ` \u00b7 ${s.status}` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isPending && <span class="spinner" />}
          <span class={`pill ${isPending ? 'pill-yellow' : isRunning ? 'pill-green' : s.status === 'failed' ? 'pill-red' : ''}`}>
            {s.status}
          </span>
        </div>
      </div>

      {isPending && <ProgressSteps sessionId={s.id} />}

      {s.url && (
        <>
          <a class="open-btn" href={s.url} target="_blank" rel="noopener">
            Open in Claude
          </a>
          <div class="open-hint">
            If it doesn't open directly, check your sessions in the Claude app.
          </div>
        </>
      )}

      <div class="actions">
        <button class="btn btn-ghost btn-sm" onClick={toggleOutput}>Output</button>
        {showKill && (isRunning || isPending) && (
          <button class="btn btn-danger btn-sm" onClick={handleKill}>Stop</button>
        )}
        {showDelete && (
          <button class="btn btn-danger btn-sm" onClick={handleDelete}>Delete</button>
        )}
      </div>

      {outputOpen && (
        <div class="output-box open">{outputText}</div>
      )}
    </article>
  );
}
