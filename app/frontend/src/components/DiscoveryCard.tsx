import type { DiscoveredEnvironment } from '../types';
import { discoveryResult, showNotice } from '../state/signals';
import { addWorkspot } from '../api/workspaces';
import { refresh } from '../state/polling';

interface Props {
  env: DiscoveredEnvironment;
}

export function DiscoveryCard({ env }: Props) {
  const isDocker = env.runtime === 'docker';
  const isUp = env.container_status?.startsWith('Up');
  const imageName = (env.image || '').split(':')[0].split('/').pop() || '';
  const meta = isDocker
    ? `${env.container || ''}${imageName ? ' \u00b7 ' + imageName : ''}`
    : 'Host runtime';
  const canAdd = !env.already_configured;

  async function handleAdd() {
    // Optimistic
    if (discoveryResult.value) {
      const dr = discoveryResult.value;
      [dr.compatible, dr.partial, dr.incompatible]
        .flat().filter(i => i.name === env.name).forEach(i => { i.already_configured = true; });
      discoveryResult.value = { ...dr };
    }
    showNotice(`Adding "${env.name}"...`);
    try {
      const r = await addWorkspot({
        name: env.name, runtime: env.runtime, dir: env.dir,
        container: env.container || undefined, claude_bin: env.claude_bin || 'claude',
        server_capacity: 32, env: {},
      });
      if (r.status !== 'ok') {
        showNotice(r.message || 'Failed.', 'error');
        return;
      }
      showNotice(`Added "${env.name}".`);
      await refresh();
    } catch { showNotice('Failed to add.', 'error'); }
  }

  return (
    <article class={`card ${env.already_configured ? 'dimmed' : ''}`}>
      <div class="card-head">
        <div>
          {env.already_configured && (
            <div style={{ marginBottom: '4px' }}>
              <span class="pill pill-tag pill-added" style={{ height: '22px' }}>In Workspaces</span>
            </div>
          )}
          <div class="card-title">{env.name}</div>
          <div class="card-meta">{meta}</div>
          {isDocker && env.container_status && (
            <div class="card-meta">{env.container_status}</div>
          )}
        </div>
        {isDocker ? (
          isUp
            ? <span class="pill pill-green" style={{ fontSize: '0.72rem', height: '24px' }}>Running</span>
            : <span class="pill" style={{ fontSize: '0.72rem', height: '24px' }}>Stopped</span>
        ) : (
          <span class="pill pill-tag" style={{ height: '24px' }}>Local</span>
        )}
      </div>
      <div class="card-path" title={env.dir}>{env.dir}</div>
      <div class="checks">
        {Object.entries(env.checks).map(([k, ok]) => {
          const label = k.replace(/_/g, ' ').replace(/ok$/, '').trim();
          return (
            <span key={k} class={`chk ${ok ? 'chk-ok' : 'chk-no'}`}>
              {ok ? '\u2713' : '\u2717'} {label}
            </span>
          );
        })}
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
          {canAdd ? '+ Add' : 'Added'}
        </button>
      </div>
    </article>
  );
}
