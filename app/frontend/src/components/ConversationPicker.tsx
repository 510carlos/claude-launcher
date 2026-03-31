import { useState, useEffect } from 'preact/hooks';
import { listConversations } from '../api/sessions';
import { fmtTime } from '../utils';
import type { Conversation } from '../types';

interface Props {
  workspot: string;
  onResume: (conversationId: string) => void;
  onCancel: () => void;
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / 1048576).toFixed(1)}MB`;
}

export function ConversationPicker({ workspot, onResume, onCancel }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    listConversations(workspot, 15)
      .then(setConversations)
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [workspot]);

  return (
    <div class="form-area open">
      <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>Resume a conversation</div>

      {loading && <div style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>Loading...</div>}

      {!loading && conversations.length === 0 && (
        <div style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>No previous conversations found.</div>
      )}

      {!loading && conversations.length > 0 && (
        <div class="conversation-list">
          {conversations.map(c => (
            <div
              key={c.session_id}
              class={`conversation-row${selected === c.session_id ? ' selected' : ''}`}
              onClick={() => setSelected(c.session_id)}
            >
              <div class="conversation-preview">{c.first_message}</div>
              <div class="conversation-meta">
                {fmtTime(c.last_modified)} &middot; {fmtSize(c.file_size)}
              </div>
            </div>
          ))}
        </div>
      )}

      <div class="actions">
        <button
          class="btn btn-primary btn-sm"
          disabled={!selected}
          onClick={() => selected && onResume(selected)}
        >
          Resume
        </button>
        <button class="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
