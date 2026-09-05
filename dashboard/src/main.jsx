import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './contexts/AuthContext'
import { capture as captureAttribution } from './lib/attribution'

// Single-purpose local tool: boot straight into the Clip Generator.
// No landing page, no marketing routing.

// Before React mounts: AuthContext rewrites the URL on auth redirects, which
// would destroy the referrer and any UTM params we still need to read.
captureAttribution();

// Never leave a silent black screen: surface boot crashes as readable text.
function showBootError(message) {
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML =
      '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;' +
      'background:#0c0c0e;color:#f5f2ea;font-family:system-ui,sans-serif;padding:24px;text-align:center">' +
      '<div><div style="font-size:15px;font-weight:600;margin-bottom:8px">OpenShorts failed to start</div>' +
      '<div style="font-size:13px;opacity:.7;max-width:520px">' + message + '</div>' +
      '<div style="font-size:12px;opacity:.5;margin-top:12px">Open DevTools console for the full error. ' +
      'Backend must run on :8000 — start it with `python main.py`.</div></div></div>';
  }
}
window.addEventListener('error', (e) => {
  if (!document.getElementById('root')?.hasChildNodes()) {
    showBootError(String(e.message || e.error || 'JavaScript error during load.'));
  }
});
window.addEventListener('unhandledrejection', (e) => {
  if (!document.getElementById('root')?.hasChildNodes()) {
    showBootError(String(e.reason?.message || e.reason || 'Failed to load.'));
  }
});

try {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <AuthProvider>
        <App />
      </AuthProvider>
    </StrictMode>,
  );
} catch (err) {
  console.error(err);
  showBootError(String(err?.message || err));
}
