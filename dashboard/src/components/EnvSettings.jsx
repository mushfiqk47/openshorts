import React, { useEffect, useState } from 'react';
import { Save, RefreshCw, Check, AlertTriangle, Eye, EyeOff, Copy, Download, ChevronDown, PlugZap } from 'lucide-react';
import { getApiUrl } from '../config';

// GPU / Pipeline keys render as a generic grid below the AI provider section.
const GROUPS = [
  {
    title: 'GPU / Performance',
    desc: 'Video encode and vision models pick GPU when available (pin cuda/nvenc to force). Transcription always runs on CUDA via NeMo-Speech.cpp.',
    fields: [
      { key: 'FFMPEG_ENCODER', label: 'Video Encoder', choices: ['auto', 'nvenc', 'x264'] },
      // ASR model: a NeMo-Speech.cpp alias (parakeet-tdt, parakeet-ctc,
      // nemotron-3.5, nemotron-en) or a local .gguf path, so free text.
      { key: 'NEMO_ASR_MODEL', label: 'ASR Model', placeholder: 'parakeet-tdt' },
      { key: 'NEMO_SPEECH_BIN', label: 'nemo-speech Path', placeholder: 'C:\\...\\NeMoSpeech\\bin\\nemo-speech.exe' },
      { key: 'YOLO_DEVICE', label: 'YOLO Device', choices: ['auto', 'cuda', 'cpu'] },
    ],
  },
  {
    title: 'Pipeline',
    desc: 'Tuning knobs, saved to .env and applied live (no restart).',
    fields: [
      { key: 'CLIP_WORKERS', label: 'Clip Workers', placeholder: '2' },
      { key: 'ASR_GPU_CONCURRENCY', label: 'ASR GPU Concurrency', placeholder: '1' },
      { key: 'DISABLE_YOUTUBE_URL', label: 'Disable YouTube URL', choices: ['true', 'false'] },
    ],
  },
  {
    title: 'Captions',
    desc: 'Default caption text size burned into clips. Subtitle-engine units, not screen pixels: 16 ≈ 4.5% of frame height (10–200).',
    fields: [
      { key: 'CAPTION_FONT_SIZE', label: 'Default Font Size', placeholder: '16' },
    ],
  },
];

// Which AI provider cards exist and the fields each one shows. The provider
// select at the top of the AI section decides which card renders; 'auto'
// shows both keyed cards since it picks whichever key is present.
const PROVIDER_CHOICES = ['auto', 'custom', 'gemini', 'openrouter', 'ollama'];

const PROVIDER_CARDS = {
  custom: {
    title: 'Custom provider',
    hint: 'Any OpenAI-compatible endpoint (tunnel, vLLM, llama.cpp server). Free Colab setup below.',
    colab: true,
    fields: [
      { key: 'AI_BASE_URL', label: 'Base URL', placeholder: 'https://...trycloudflare.com/v1' },
      { key: 'AI_API_KEY', label: 'API Key', placeholder: 'sk-...', secret: true },
      { key: 'AI_MODEL', label: 'Model', placeholder: 'mimo-v2.6-heretic' },
    ],
  },
  openrouter: {
    title: 'OpenRouter',
    hint: 'Free shared models with a sk-or-... key.',
    fields: [
      { key: 'OPENROUTER_API_KEY', label: 'API Key', placeholder: 'sk-or-v1-...', secret: true },
      { key: 'OPENROUTER_MODEL', label: 'Model', placeholder: 'z-ai/glm-5.2:free' },
    ],
  },
  gemini: {
    title: 'Gemini',
    hint: 'Google AI Studio key; also runs silent-video vision.',
    fields: [
      { key: 'GEMINI_API_KEY', label: 'API Key', placeholder: 'AIza...', secret: true },
    ],
  },
  ollama: {
    title: 'Ollama (local)',
    hint: 'Fully local via the OpenAI-compatible endpoint on this machine.',
    fields: [
      { key: 'OLLAMA_MODEL', label: 'Model', placeholder: 'lfm3-vl:2b-q4_K_M' },
      { key: 'OLLAMA_URL', label: 'URL', placeholder: 'http://localhost:11434' },
    ],
  },
};

const ALL_FIELDS = [
  ...GROUPS.flatMap(g => g.fields),
  ...Object.values(PROVIDER_CARDS).flatMap(c => c.fields),
];

const isSecretKey = (k) => ALL_FIELDS.some(f => f.key === k && f.secret);

// One labeled control. Secrets get an eye toggle and, once a value exists,
// a copy button (copying the masked empty state would be useless).
function EnvField({ f, value, placeholder, isSet, onChange, showSecret, onToggleSecret, copiedKey, onCopy }) {
  const isSecret = !!f.secret;
  return (
    <label className="block">
      <span className="text-xs text-ink2 font-medium">{f.label} <span className="font-mono text-[11px] text-muted/70">{f.key}</span>{isSet && <span className="ml-1 text-ok text-[11px]">• set</span>}</span>
      {f.choices ? (
        <select value={value || (f.choices[0])} onChange={e => onChange(f.key, e.target.value)} className="input-field mt-1.5 font-mono text-sm">
          {f.choices.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      ) : (
        <div className="relative mt-1.5">
          <input
            type={isSecret && !showSecret[f.key] ? 'password' : 'text'}
            value={value}
            onChange={e => onChange(f.key, e.target.value)}
            placeholder={isSecret ? (isSet ? placeholder : f.placeholder) : f.placeholder}
            className={`input-field font-mono text-sm ${isSecret ? 'pr-16' : ''}`}
          />
          {isSecret && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
              {value ? (
                <button type="button" onClick={onCopy} title="Copy value" className="text-muted hover:text-ink">
                  {copiedKey === f.key ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
                </button>
              ) : null}
              <button type="button" onClick={onToggleSecret} className="text-muted hover:text-ink">
                {showSecret[f.key] ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </span>
          )}
        </div>
      )}
    </label>
  );
}

// Free-GPU path for the custom provider: the Colab notebook below spins up a
// model behind a public OpenAI-compatible URL and prints exactly the values
// this card asks for. The .ipynb is a static asset in dashboard/public.
const NOTEBOOK_URL = `${import.meta.env.BASE_URL}mimo_v26_heretic_ollama_colab.ipynb`;

function ColabGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-rule rounded-card bg-paper3 p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs text-muted leading-relaxed">
          No paid AI key? Run <span className="text-ink font-medium">mimo-v2.6-heretic</span> free on Google Colab — the notebook prints the Base URL and API key to paste into this card.
        </p>
        <a href={NOTEBOOK_URL} download className="btn-quiet py-1.5 px-3 text-xs shrink-0">
          <Download size={13} /> Download notebook
        </a>
      </div>
      <button type="button" onClick={() => setOpen(o => !o)} className="mt-2 inline-flex items-center gap-1 text-xs text-brass hover:underline">
        {open ? 'Hide setup steps' : 'How to set it up'}
        <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <>
          <ol className="mt-2 space-y-1.5 text-xs text-muted leading-relaxed list-decimal list-inside">
            <li>Download the notebook, then open it on <a href="https://colab.research.google.com/" target="_blank" rel="noreferrer" className="text-brass hover:underline">Google Colab</a> (File → Upload notebook).</li>
            <li>Runtime → Change runtime type → <span className="text-ink2">T4 GPU</span>, then Run all (~5 min: installs Ollama, pulls the 9B model, starts a Cloudflare tunnel).</li>
            <li>The output prints a <span className="text-ink2">Base URL</span> (<code className="font-mono">https://….trycloudflare.com/v1</code>) and an <span className="text-ink2">API key</span> — copy both.</li>
            <li>Paste them here: Base URL → <code className="font-mono">AI_BASE_URL</code>, API Key → <code className="font-mono">AI_API_KEY</code>, Model → <code className="font-mono">mimo-v2.6-heretic</code>, then Save.</li>
          </ol>
          <p className="mt-2 text-[11px] text-muted/80 leading-relaxed">
            Free Colab disconnects after ~12h and every re-run gets a new URL — update Base URL when that happens. Thinking is off by default; the notebook's docs show how to turn it on per request.
          </p>
        </>
      )}
    </div>
  );
}


// Transcription models: drives the nemo-speech runtime (list / download /
// smoke test). Independent of the AI analysis provider above — this is the
// ASR (parakeet) side of the pipeline.
function TranscriptionModels() {
  const [models, setModels] = useState(null);
  const [active, setActive] = useState('');
  const [job, setJob] = useState(null);
  const [err, setErr] = useState(null);

  const load = async () => {
    try {
      const res = await fetch(getApiUrl('/api/asr/models'));
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setModels(data.models);
      setActive(data.active);
      setJob(data.job);
      setErr(null);
    } catch (e) {
      setErr(e.message);
    }
  };

  useEffect(() => {
    load();
    const timer = setInterval(async () => {
      try {
        const s = await (await fetch(getApiUrl('/api/asr/status'))).json();
        setJob(s);
        if (!s.running) load();
      } catch { /* ignore poll errors */ }
    }, 2500);
    return () => clearInterval(timer);
  }, []);

  const act = async (path, body) => {
    setErr(null);
    try {
      const res = await fetch(getApiUrl(path), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      });
      if (!res.ok) throw new Error(await res.text());
      setTimeout(load, 400);
    } catch (e) {
      setErr(e.message);
    }
  };

  const running = job?.running;

  return (
    <div className="mt-6">
      <h3 className="text-sm font-medium text-ink lowercase">transcription models</h3>
      <p className="text-xs text-muted mb-3">The ASR brain (NeMo-Speech.cpp on CUDA). Download a model here or let the first job pull it automatically; the smoke test proves the whole GPU chain before you upload anything.</p>
      {err && <p className="text-xs text-warn mb-2">{err}</p>}
      {!models ? (
        <p className="text-xs text-muted flex items-center gap-2"><RefreshCw size={12} className="animate-spin" /> reading the runtime…</p>
      ) : (
        <div className="border border-rule rounded-card bg-paper2 p-4 space-y-2">
          {models.map(m => {
            const isActive = active === m.alias || (m.aliases || []).includes(active);
            return (
              <div key={m.alias} className={`flex items-center justify-between gap-3 p-2 rounded-input ${isActive ? 'bg-paper3' : ''}`}>
                <div className="min-w-0">
                  <span className="text-sm text-ink font-mono">{m.alias}</span>
                  {isActive && <span className="readout ml-2">active</span>}
                  <span className={`ml-2 text-[11px] ${m.cached ? 'text-ok' : 'text-muted'}`}>{m.cached ? '• downloaded' : '• not downloaded'}</span>
                </div>
                <button
                  onClick={() => act('/api/asr/download', { model: m.alias })}
                  disabled={running || m.cached}
                  className="btn-quiet py-1.5 px-3 text-xs disabled:opacity-50 shrink-0"
                  title={m.cached ? 'Already downloaded' : 'Download from Hugging Face (sha256 verified)'}
                >
                  {m.cached ? 'downloaded' : 'download'}
                </button>
              </div>
            );
          })}
          <div className="pt-2 border-t border-rule flex items-center justify-between gap-3">
            <span className="text-xs text-muted">
              {running
                ? `working: ${job?.model || 'smoke test'}…`
                : job?.ok === true
                  ? 'last check passed'
                  : job?.ok === false
                    ? <span className="text-warn">last check failed: {String(job?.detail || '').slice(0, 120)}</span>
                    : 'run the smoke test to verify the GPU chain'}
            </span>
            <button onClick={() => act('/api/asr/smoke-test')} disabled={running} className="btn-primary py-1.5 px-3 text-xs disabled:opacity-50 shrink-0">
              {running ? 'working…' : 'test transcription'}
            </button>
          </div>
          {job?.detail && !running && job?.ok === true && (
            <p className="text-[11px] font-mono text-muted break-all">{String(job.detail).slice(0, 200)}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function EnvSettings() {
  const [env, setEnv] = useState(null);
  const [secretsSet, setSecretsSet] = useState({});
  const [allowed, setAllowed] = useState([]);
  const [draft, setDraft] = useState({});
  const [secretDraft, setSecretDraft] = useState({});
  const [showSecret, setShowSecret] = useState({});
  const [copiedKey, setCopiedKey] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [testState, setTestState] = useState({ status: 'idle', msg: '' });

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
    if (isSecretKey(k)) {
      setSecretDraft(prev => ({ ...prev, [k]: v }));
    } else {
      setDraft(prev => ({ ...prev, [k]: v }));
    }
  };

  const copyValue = async (key, value) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(k => (k === key ? null : k)), 1200);
    } catch { /* clipboard unavailable — no-op */ }
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
      setMsg('Saved to .env, applied live (no restart needed).');
      setEnv(data.env);
      setSecretsSet(data.secretsSet || {});
      const d = { ...draft };
      for (const k of Object.keys(updates)) {
        d[k] = isSecretKey(k) ? '' : (data.env[k] || '');
      }
      setDraft(d);
      setSecretDraft({});
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  // Ping the active AI provider through the backend. Draft values (including
  // just-typed secrets) are sent so the test reflects the form, not the last
  // save; anything left empty falls back to the saved .env on the server.
  const testConnection = async () => {
    setTestState({ status: 'testing', msg: '' });
    const prov = draft['AI_PROVIDER'] || env?.['AI_PROVIDER'] || 'auto';
    const updates = { AI_PROVIDER: prov };
    const cardsToTest = prov === 'auto'
      ? [PROVIDER_CARDS.openrouter, PROVIDER_CARDS.gemini]
      : [PROVIDER_CARDS[prov]].filter(Boolean);
    for (const card of cardsToTest) {
      for (const f of card.fields) {
        const v = f.secret ? (secretDraft[f.key] ?? '') : (draft[f.key] ?? '');
        if (String(v).trim()) updates[f.key] = String(v).trim();
      }
    }
    try {
      const res = await fetch(getApiUrl('/api/ai/test'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (data.ok) {
        const secs = (data.latencyMs / 1000).toFixed(1);
        setTestState({ status: 'ok', msg: `connected — ${data.model} · ${secs}s` });
      } else {
        setTestState({ status: 'fail', msg: (data.error || 'connection failed').slice(0, 180) });
      }
    } catch (e) {
      setTestState({ status: 'fail', msg: String(e.message || e).slice(0, 180) });
    }
  };

  if (loading) return <div className="card p-6 text-sm text-muted flex items-center gap-2"><RefreshCw size={14} className="animate-spin" /> Loading env from .env…</div>;
  if (err && !env) return <div className="card p-4 text-sm text-warn flex items-center gap-2"><AlertTriangle size={14} /> {err} <button onClick={load} className="ml-auto btn-quiet py-1 px-3 text-xs">Retry</button></div>;

  const provider = draft['AI_PROVIDER'] || env?.['AI_PROVIDER'] || 'auto';
  const cards = provider === 'auto'
    ? [PROVIDER_CARDS.openrouter, PROVIDER_CARDS.gemini]
    : [PROVIDER_CARDS[provider]];

  const fieldProps = (f) => ({
    f,
    value: f.secret ? (secretDraft[f.key] ?? '') : (draft[f.key] ?? ''),
    isSet: f.secret ? secretsSet[f.key] : false,
    onChange: setField,
    showSecret,
    onToggleSecret: () => setShowSecret(p => ({ ...p, [f.key]: !p[f.key] })),
    copiedKey,
    onCopy: () => copyValue(f.key, f.secret ? (secretDraft[f.key] ?? '') : (draft[f.key] ?? '')),
  });

  return (
    <div className="space-y-6">
      <div className="card p-4 sm:p-6">
        <div className="flex items-center justify-between gap-2 mb-1">
          <h2 className="font-display font-medium lowercase text-lg text-ink">Environment (.env)</h2>
          <span className="text-xs font-mono text-muted">{env ? `${allowed.length} keys` : ''}</span>
        </div>
        <p className="text-xs text-muted leading-relaxed mb-4">Project follows the <code className="font-mono bg-paper3 px-1 rounded">.env</code> file. Editing here writes the file and applies live. Manual file edits are also picked up (dashboard reads the file on load).</p>

        {/* AI provider: dropdown first, then only the selected provider's card */}
        <div className="mt-6 first:mt-2">
          <h3 className="text-sm font-medium text-ink lowercase">ai provider</h3>
          <p className="text-xs text-muted mb-3">Which service picks the viral moments. Everything writes to .env and applies live.</p>
          <div className="max-w-xl">
            <EnvField f={{ key: 'AI_PROVIDER', label: 'AI Provider', choices: PROVIDER_CHOICES }} value={draft['AI_PROVIDER'] ?? ''} placeholder={null} isSet={false} onChange={setField} showSecret={{}} onToggleSecret={() => {}} copiedKey={null} onCopy={() => {}} />
          </div>
          <p className="text-xs text-muted mt-2">Only the selected provider's fields are shown.{provider === 'auto' ? ' Auto uses OpenRouter when its key is set, else Gemini.' : ''}</p>
          <div className="space-y-3 mt-3">
            {cards.map(card => (
              <div key={card.title} className="border border-rule rounded-card bg-paper2 p-4">
                <h4 className="text-sm font-semibold text-ink">{card.title}</h4>
                <p className="text-xs text-muted mt-0.5 mb-3">{card.hint}</p>
                <div className="space-y-3">
                  {card.fields.map(f => <EnvField key={f.key} {...fieldProps(f)} />)}
                </div>
                {card.colab && <ColabGuide />}
              </div>
            ))}
          </div>

          {/* Connection test: pings the active provider with the form's draft
              values, so credentials can be verified before they are saved. */}
          <div className="mt-3 flex items-center gap-3 flex-wrap min-w-0">
            <button type="button" onClick={testConnection} disabled={testState.status === 'testing'} className="btn-quiet py-2 px-4 text-sm disabled:opacity-60">
              {testState.status === 'testing'
                ? <><RefreshCw size={14} className="animate-spin" /> Testing…</>
                : <><PlugZap size={14} /> Test connection</>}
            </button>
            {testState.status === 'ok' && (
              <p className="text-xs text-ok flex items-center gap-1 min-w-0"><Check size={12} className="shrink-0" /> {testState.msg}</p>
            )}
            {testState.status === 'fail' && (
              <p className="text-xs text-warn flex items-center gap-1 min-w-0"><AlertTriangle size={12} className="shrink-0" /> <span className="truncate" title={testState.msg}>{testState.msg}</span></p>
            )}
          </div>
        </div>

        <TranscriptionModels />

        {GROUPS.map(group => (
          <div key={group.title} className="mt-6">
            <h3 className="text-sm font-medium text-ink lowercase">{group.title}</h3>
            <p className="text-xs text-muted mb-3">{group.desc}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {group.fields.map(f => <EnvField key={f.key} {...fieldProps(f)} />)}
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
