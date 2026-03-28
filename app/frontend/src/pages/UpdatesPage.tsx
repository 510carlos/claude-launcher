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
        setResult(r.message || 'Update failed.');
      }
    } catch {
      setResult('Update failed.');
    } finally {
      setApplying(false);
    }
  }

  useEffect(() => { handleCheck(); }, []);

  return (
    <>
      <div class="section-head" style={{ marginBottom: '4px' }}>
        <span class="section-title">Updates</span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button class="btn btn-ghost btn-sm" onClick={handleCheck} disabled={checking}>
            {checking ? 'Checking\u2026' : 'Check'}
          </button>
          <button class="btn btn-ghost btn-sm" onClick={() => {
            route.value = '/';
            window.location.hash = '#/';
          }}>Back</button>
        </div>
      </div>

      {result && (
        <div class="notice info" style={{ display: 'block' }}>{result}</div>
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
    </>
  );
}
