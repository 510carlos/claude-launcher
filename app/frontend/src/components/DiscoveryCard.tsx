import type { DiscoveredEnvironment } from '../types';
import { discoveryResult, showNotice } from '../state/signals';
import { addWorkspot } from '../api/workspaces';
import { refresh } from '../state/polling';

interface Props {
  env: DiscoveredEnvironment;
}

export function DiscoveryCard({ env }: Props) {
  const canAdd = !env.already_configured;
  const isReady = env.compatibility === 'compatible';

  async function handleAdd() {
    if (discoveryResult.value) {
      const dr = discoveryResult.value;
      [dr.compatible, dr.partial, dr.incompatible]
        .flat().filter(i => i.name === env.name).forEach(i => { i.already_configured = true; });
      discoveryResult.value = { ...dr };
    }
    try {
      const r = await addWorkspot({
        name: env.name, runtime: env.runtime, dir: env.dir,
        container: env.container || undefined, claude_bin: env.claude_bin || 'claude',
        server_capacity: 32, env: {},
      });
      if (r.status !== 'ok') {
        showNotice(r.message || 'Failed to add workspace.', 'error');
        return;
      }
      await refresh();
    } catch { showNotice('Failed to add.', 'error'); }
  }

  return (
    <article class={`card ${env.already_configured ? 'dimmed' : ''}`}>
      <div class="card-head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <div class="card-title">{env.name}</div>
          <div class="card-path" title={env.dir} style={{ marginTop: '6px' }}>{env.dir}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
          {env.already_configured
            ? <span class="pill pill-tag pill-added" style={{ height: '24px' }}>Added</span>
            : isReady
              ? <span class="pill pill-green pill-plain" style={{ height: '24px' }}>Ready</span>
              : <span class="pill pill-plain" style={{ height: '24px' }}>Needs setup</span>
          }
          {env.activity_label && (
            <span style={{ color: 'var(--muted)', fontSize: '0.72rem', textAlign: 'right' }}>{env.activity_label}</span>
          )}
        </div>
      </div>

      <div class="checks">
        {Object.entries(env.checks).map(([k, ok]) => {
          const label = k.replace(/_/g, ' ').replace(/ok$/, '').trim();
          return (
            <span key={k} class={`chk ${ok ? 'chk-ok' : 'chk-no'}`}>
              {ok ? '✓' : '✗'} {label}
            </span>
          );
        })}
        {env.has_claude_setup && (
          <span class="chk chk-ok">✓ claude setup</span>
        )}
      </div>

      {env.issues.length > 0 && (
        <div class="errors">
          {env.issues.map((issue, i) => <div key={i} class="err">{issue}</div>)}
        </div>
      )}

      <div class="actions">
        <button
          class={`btn ${canAdd ? 'btn-primary' : 'btn-ghost'} btn-sm`}
          onClick={handleAdd} disabled={!canAdd}
        >
          {canAdd ? '+ Add to Workspaces' : 'Already added'}
        </button>
      </div>
    </article>
  );
}
