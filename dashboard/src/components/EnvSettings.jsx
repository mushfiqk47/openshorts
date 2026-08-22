import React, { useEffect, useState } from 'react';
import { Save, RefreshCw, Check, AlertTriangle, Eye, EyeOff } from 'lucide-react';
import { getApiUrl } from '../config';

const GROUPS = [
  {
    title: 'AI Keys',
    desc: 'Also saved to .env so the backend uses them without the browser header. Changing here writes the file immediately.',
    fields: [
      { key: 'OPENROUTER_API_KEY', label: 'OpenRouter API Key', placeholder: 'sk-or-v1-...', secret: true },
      { key: 'OPENROUTER_MODEL', label: 'OpenRouter Model', placeholder: 'z-ai/glm-5.2:free', choices: null },
      { key: 'GEMINI_API_KEY', label: 'Gemini API Key', placeholder: 'AIza...', secret: true },
    ],
  },
  {
    title: 'GPU / Performance',
    desc: 'GPU-first: auto uses GPU when available, CPU otherwise. Pin to cuda/x264 to force.',
    fields: [
      { key: 'FFMPEG_ENCODER', label: 'Video Encoder', choices: ['auto', 'nvenc', 'x264'] },
      { key: 'WHISPER_DEVICE', label: 'Whisper Device', choices: ['auto', 'cuda', 'cpu'] },
      { key: 'WHISPER_COMPUTE', label: 'Whisper Compute', choices: ['auto', 'float16', 'float32', 'int8', 'int8_float16'] },
      { key: 'YOLO_DEVICE', label: 'YOLO Device', choices: ['auto', 'cuda', 'cpu'] },
      { key: 'WHISPER_MODEL', label: 'Whisper Model', placeholder: 'small', choices: ['small', 'base', 'medium', 'large-v3-turbo'] },
    ],
  },
  {
    title: 'Pipeline',
    desc: 'Tuning knobs — saved to .env and applied live (no restart).',
    fields: [
      { key: 'CLIP_WORKERS', label: 'Clip Workers', placeholder: '2' },
      { key: 'ASR_GPU_CONCURRENCY', label: 'ASR GPU Concurrency', placeholder: '1' },
      { key: 'DISABLE_YOUTUBE_URL', label: 'Disable YouTube URL', choices: ['true', 'false'] },
    ],
  },
];

export default function EnvSettings() {
  const [env, setEnv] = useState(null);
  const [secretsSet, setSecretsSet] = useState({});
  const [allowed, setAllowed] = useState([]);
  const [draft, setDraft] = useState({});
  const [secretDraft, setSecretDraft] = useState({});
  const [showSecret, setShowSecret] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(getApiUrl('/api/env'));
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setEnv(data.env);
      setSecretsSet(data.secretsSet || {});
      setAllowed(data.allowed || []);
      // Draft starts as live values (except secrets -> empty)
      const d = {};
      for (const [k, v] of Object.entries(data.env || {})) {
        if (data.secretsSet?.[k]) d[k] = ''; // secret masked -> keep empty until user types
        else d[k] = v || '';
      }
      // Keep existing secretDraft empty so we don't overwrite with mask
      setDraft(d);
      setSecretDraft({});
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const setField = (k, v) => {
    if (GROUPS.some(g => g.fields.some(f => f.key === k && f.secret))) {
      setSecretDraft(prev => ({ ...prev, [k]: v }));
    } else {
      setDraft(prev => ({ ...prev, [k]: v }));
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    setErr(null);
    try {
      const updates = {};
      // Non-secrets: send if changed from env
      for (const [k, v] of Object.entries(draft)) {
        const live = env?.[k] || '';
        // For secrets we handle separately
        if (secretsSet[k]) continue;
        if (String(v) !== String(live)) updates[k] = v;
      }
      // Secrets: only send if user typed something
      for (const [k, v] of Object.entries(secretDraft)) {
        if (v && String(v).trim()) updates[k] = v.trim();
      }
      if (Object.keys(updates).length === 0) {
        setMsg('No changes to save.');
        setSaving(false);
        return;
      }
      const res = await fetch(getApiUrl('/api/env'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      });
      if (!res.ok) {
        const t = await res.text();
        try { const j = JSON.parse(t); throw new Error(j.detail?.validation ? JSON.stringify(j.detail.validation) : j.detail || t); } catch { throw new Error(t); }
      }
      const data = await res.json();
      setMsg('Saved to .env — applied live (no restart needed).');
      // Reload
      setEnv(data.env);
      setSecretsSet(data.secretsSet || {});
      const d = { ...draft };
      for (const k of Object.keys(updates)) {
        if (secretsSet[k] || GROUPS.some(g => g.fields.some(f => f.key === k && f.secret))) {
          d[k] = '';
        } else {
          d[k] = data.env[k] || '';
        }
      }
      setDraft(d);
      setSecretDraft({});
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="card p-6 text-sm text-muted flex items-center gap-2"><RefreshCw size={14} className="animate-spin" /> Loading env from .env…</div>;
  if (err && !env) return <div className="card p-4 text-sm text-warn flex items-center gap-2"><AlertTriangle size={14} /> {err} <button onClick={load} className="ml-auto btn-quiet py-1 px-3 text-xs">Retry</button></div>;

  return (
    <div className="space-y-6">
      <div className="card p-4 sm:p-6">
        <div className="flex items-center justify-between gap-2 mb-1">
          <h2 className="font-display lowercase text-lg text-ink">Environment (.env)</h2>
          <span className="text-xs font-mono text-muted">{env ? `${allowed.length} keys` : ''}</span>
        </div>
        <p className="text-xs text-muted leading-relaxed mb-4">Project follows the <code className="font-mono bg-paper3 px-1 rounded">.env</code> file. Editing here writes the file and applies live — manual file edits are also picked up (dashboard reads the file on load).</p>
        {GROUPS.map(group => (
          <div key={group.title} className="mt-6 first:mt-2">
            <h3 className="text-sm font-medium text-ink lowercase">{group.title}</h3>
            <p className="text-xs text-muted mb-3">{group.desc}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {group.fields.map(f => {
                const isSecret = !!f.secret;
                const value = isSecret ? (secretDraft[f.key] ?? '') : (draft[f.key] ?? '');
                const masked = env?.[f.key] || '';
                const isSet = isSecret ? secretsSet[f.key] : false;
                return (
                  <label key={f.key} className="block">
                    <span className="text-xs text-muted">{f.label} <span className="font-mono text-[11px] text-muted/70">{f.key}</span>{isSet && <span className="ml-1 text-ok text-[11px]">• set</span>}</span>
                    {f.choices ? (
                      <select value={value || (f.choices[0])} onChange={e => setField(f.key, e.target.value)} className="input-field mt-1 font-mono text-sm">
                        {f.choices.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    ) : (
                      <div className="relative mt-1">
                        <input
                          type={isSecret && !showSecret[f.key] ? 'password' : 'text'}
                          value={value}
                          onChange={e => setField(f.key, e.target.value)}
                          placeholder={isSecret ? (isSet ? masked : f.placeholder) : f.placeholder}
                          className="input-field pr-9 font-mono text-sm"
                        />
                        {isSecret && (
                          <button type="button" onClick={() => setShowSecret(p => ({ ...p, [f.key]: !p[f.key] }))} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-ink">
                            {showSecret[f.key] ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        )}
                      </div>
                    )}
                  </label>
                );
              })}
            </div>
          </div>
        ))}
        {msg && <p className="mt-4 text-xs text-ok flex items-center gap-1"><Check size={12} /> {msg}</p>}
        {err && <p className="mt-4 text-xs text-warn flex items-center gap-1"><AlertTriangle size={12} /> {err}</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          <button onClick={handleSave} disabled={saving} className="btn-primary py-2 px-4 text-sm disabled:opacity-60">
            {saving ? <><RefreshCw size={14} className="animate-spin" /> Saving…</> : <><Save size={14} /> Save to .env</>}
          </button>
          <button onClick={load} disabled={saving} className="btn-quiet py-2 px-4 text-sm">Reload from file</button>
        </div>
        <p className="mt-3 text-[11px] text-muted">Writes <code className="font-mono">.env</code> in the project root. Emptying a secret clears it from the file.</p>
      </div>
    </div>
  );
}
