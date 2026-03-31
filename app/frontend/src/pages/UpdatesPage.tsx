import { useState, useEffect } from 'preact/hooks';
import { route } from '../state/signals';
import { checkUpdates, applyUpdate } from '../api/updates';
import type { UpdateCheck } from '../api/updates';

export function UpdatesPage() {
  const [check, setCheck] = useState<UpdateCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleCheck() {
    setChecking(true);
    setResult(null);
    try {
      const r = await checkUpdates();
      setCheck(r);
    } catch {
      setResult('Failed to check for updates.');
    } finally {
      setChecking(false);
    }
  }

  async function handleApply() {
    setApplying(true);
    setResult(null);
    try {
      const r = await applyUpdate();
      if (r.status === 'ok') {
        setResult('Update applied! App is restarting\u2026');
        setTimeout(() => window.location.reload(), 4000);
      } else {
        const detail = r.steps?.filter(s => !s.ok).map(s => s.output).join('\n') || '';
        setResult((r.message || 'Update failed.') + (detail ? `\n${detail}` : ''));
      }
    } catch {
      setResult('Update failed.');
    } finally {
      setApplying(false);
    }
  }

  useEffect(() => { handleCheck(); }, []);

  return (
    <div class="content-narrow">
      <div class="section-head" style={{ marginBottom: '4px' }}>
        <span class="section-title">Updates</span>
        <button class="btn btn-ghost btn-sm" onClick={handleCheck} disabled={checking}>
          {checking ? 'Checking\u2026' : 'Check'}
        </button>
      </div>

      {result && (
        <div class="notice info" style={{ display: 'block', whiteSpace: 'pre-wrap' }}>{result}</div>
      )}

      {check && (
        <div class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">
                {check.behind === 0 ? 'Up to date' : `${check.behind} update${check.behind > 1 ? 's' : ''} available`}
              </div>
              <div class="panel-sub">Current: {check.current}</div>
            </div>
            {check.behind > 0 && (
              <span class="pill pill-yellow pill-plain">{check.behind} behind</span>
            )}
            {check.behind === 0 && (
              <span class="pill pill-green pill-plain">latest</span>
            )}
          </div>

          {check.behind > 0 && (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {check.commits.map((c, i) => (
                  <div key={i} class="card-path" style={{ whiteSpace: 'normal', wordBreak: 'break-word' }}>{c}</div>
                ))}
              </div>
              <button
                class="btn btn-primary btn-full"
                onClick={handleApply}
                disabled={applying}
              >
                {applying ? 'Updating\u2026' : 'Pull & Restart'}
              </button>
            </>
          )}
        </div>
      )}

      {!check && !checking && (
        <div class="empty">Could not check for updates.</div>
      )}

      <div class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">Reset App Cache</div>
            <div class="panel-sub">Clears cached assets so the home screen shortcut picks up new icons and name.</div>
          </div>
        </div>
        <button class="btn btn-danger btn-full" onClick={async () => {
          try {
            const keys = await caches.keys();
            await Promise.all(keys.map(k => caches.delete(k)));
            const reg = await navigator.serviceWorker?.getRegistration();
            if (reg) await reg.unregister();
            localStorage.clear();
            setResult('Cache cleared! Delete your home screen shortcut and re-add it to get the new icon/name.');
          } catch {
            setResult('Failed to clear cache.');
          }
        }}>
          {'\u{1F5D1}'} Clear Cache
        </button>
      </div>
    </div>
  );
}
