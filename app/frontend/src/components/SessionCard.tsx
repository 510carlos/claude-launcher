import { useState } from 'preact/hooks';
import type { Session } from '../types';
import { fmtTime, sessionIdentity } from '../utils';
import { deleteSession as apiDelete, getSessionOutput } from '../api/sessions';
import { sessions, showNotice } from '../state/signals';
import { refresh } from '../state/polling';

interface Props {
  session: Session;
  showDelete?: boolean;
}

export function SessionCard({ session: s, showDelete = false }: Props) {
  const [outputOpen, setOutputOpen] = useState(false);
  const [outputText, setOutputText] = useState('');

  const identity = sessionIdentity(s.workspot, s.branch);
  const time = fmtTime(s.created_at);
  const attachCommand = typeof s.metadata?.attach_command === 'string' ? s.metadata.attach_command : null;

  async function copyAttach() {
    if (!attachCommand) return;
    try {
      await navigator.clipboard.writeText(attachCommand);
      showNotice('Attach command copied.');
    } catch { showNotice('Copy failed.', 'error'); }
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
            {s.label ? `${s.label} \u00b7 ` : ''}{time} &middot; {s.status}
          </div>
        </div>
        <span class={`pill ${s.status === 'failed' ? 'pill-red' : ''}`}>{s.status}</span>
      </div>

      <div class="actions">
        <button class="btn btn-ghost btn-sm" onClick={toggleOutput}>Output</button>
        {attachCommand && (
          <button class="btn btn-ghost btn-sm" onClick={copyAttach}>Copy attach</button>
        )}
        {showDelete && (
          <button class="btn btn-danger btn-sm" onClick={handleDelete}>Delete</button>
        )}
      </div>

      {attachCommand && (
        <div class="card-meta" style="margin-top:6px;font-family:monospace;word-break:break-all;opacity:0.8">{attachCommand}</div>
      )}

      {outputOpen && (
        <div class="output-box open">{outputText}</div>
      )}
    </article>
  );
}
