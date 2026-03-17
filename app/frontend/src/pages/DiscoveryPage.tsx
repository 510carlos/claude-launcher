import { discoveryResult, scanning, showNotice, route } from '../state/signals';
import { runDiscovery as apiDiscover } from '../api/discovery';
import { DiscoveryCard } from '../components/DiscoveryCard';

export function DiscoveryPage() {
  const result = discoveryResult.value;
  const isScanning = scanning.value;

  async function handleScan() {
    scanning.value = true;
    discoveryResult.value = null;
    showNotice('Scanning...');
    try {
      const r = await apiDiscover();
      discoveryResult.value = r;
      showNotice(`Found ${r.total} environments, ${r.compatible.length} compatible.`);
    } catch {
      showNotice('Discovery failed.', 'error');
    } finally {
      scanning.value = false;
    }
  }

  // Auto-scan on first visit
  if (!result && !isScanning) {
    handleScan();
  }

  return (
    <>
      <div class="section-head" style={{ marginBottom: '4px' }}>
        <span class="section-title">Discover Environments</span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button class="btn btn-primary btn-sm" onClick={handleScan} disabled={isScanning}>
            {isScanning ? 'Scanning...' : 'Rescan'}
          </button>
          <button class="btn btn-ghost btn-sm" onClick={() => {
            route.value = '/';
            window.location.hash = '#/';
          }}>Back</button>
        </div>
      </div>
      <div style={{ color: 'var(--muted)', fontSize: '0.82rem', marginBottom: '10px' }}>
        Scans Docker containers and local repos. Add compatible ones to your workspaces.
      </div>

      {isScanning && (
        <div class="notice info" style={{ display: 'block' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span class="spinner" /> Scanning environments...
          </div>
        </div>
      )}

      {result && result.compatible.length > 0 && (
        <div class="panel">
          <div class="panel-head">
            <div><div class="panel-title">Compatible</div><div class="panel-sub">Ready to use.</div></div>
            <span class="pill pill-green pill-plain">{result.compatible.length}</span>
          </div>
          <div class="grid">
            {result.compatible.map(e => <DiscoveryCard key={e.name} env={e} />)}
          </div>
        </div>
      )}

      {result && result.partial.length > 0 && (
        <div class="panel">
          <div class="panel-head">
            <div><div class="panel-title">Needs Setup</div><div class="panel-sub">Missing requirements.</div></div>
            <span class="pill pill-yellow pill-plain">{result.partial.length}</span>
          </div>
          <div class="grid">
            {result.partial.map(e => <DiscoveryCard key={e.name} env={e} />)}
          </div>
        </div>
      )}

      {result && result.incompatible.length > 0 && (
        <div class="panel">
          <div class="panel-head">
            <div><div class="panel-title">Not Ready</div><div class="panel-sub">Missing most requirements.</div></div>
            <span class="pill pill-plain">{result.incompatible.length}</span>
          </div>
          <div class="grid">
            {result.incompatible.map(e => <DiscoveryCard key={e.name} env={e} />)}
          </div>
        </div>
      )}

      {!result && !isScanning && (
        <div class="empty">No scan results yet.</div>
      )}
    </>
  );
}
