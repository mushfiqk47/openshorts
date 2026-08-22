import React, { useState, useEffect } from 'react';
import { Key, Eye, EyeOff, Check, RefreshCw, Loader2 } from 'lucide-react';
import { getApiUrl } from '../config';

const FALLBACK_FREE_MODELS = [
    "openrouter/free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
];

export default function KeyInput({ onKeySet, savedKey }) {
    const [key, setKey] = useState(savedKey || '');
    const [isVisible, setIsVisible] = useState(false);
    const [isSaved, setIsSaved] = useState(!!savedKey);
    const isOR = key.trim().startsWith('sk-or-v1-') || key.trim().startsWith('sk-or-');
    const [orModel, setOrModel] = useState(() => {
        try { return localStorage.getItem('openrouter_model') || FALLBACK_FREE_MODELS[0]; } catch { return FALLBACK_FREE_MODELS[0]; }
    });
    const [freeModels, setFreeModels] = useState(FALLBACK_FREE_MODELS);
    const [loadingModels, setLoadingModels] = useState(false);
    const [modelsError, setModelsError] = useState(null);

    const fetchFreeModels = async (apiKey = key) => {
        setLoadingModels(true);
        setModelsError(null);
        try {
            const headers = {};
            if (apiKey && apiKey.trim().startsWith('sk-or-')) {
                headers['X-OpenRouter-Key'] = apiKey.trim();
            }
            const res = await fetch(getApiUrl('/api/openrouter/models'), { headers });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            const ids = (data.models || []).map(m => m.id).filter(Boolean);
            if (ids.length > 0) {
                setFreeModels(ids);
                // If current selection is not in the new list, keep it but don't auto-switch (respect user choice)
                // If it's still the fallback default and fallback not in list, switch to first live model
                if (!ids.includes(orModel) && FALLBACK_FREE_MODELS.includes(orModel)) {
                    const first = ids[0];
                    setOrModel(first);
                    try { localStorage.setItem('openrouter_model', first); } catch {}
                }
            }
        } catch (e) {
            setModelsError(e.message || 'Failed to load');
            setFreeModels(FALLBACK_FREE_MODELS);
        } finally {
            setLoadingModels(false);
        }
    };

    useEffect(() => {
        // Auto-detect on mount and when key becomes an OR key (debounced)
        if (isOR) {
            const t = setTimeout(() => fetchFreeModels(key), 400);
            return () => clearTimeout(t);
        } else if (!key) {
            // No key yet — still try to load via server env key
            fetchFreeModels('');
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOR]);

    useEffect(() => {
        if (savedKey) setKey(savedKey);
    }, [savedKey]);

    const handleSave = async () => {
        if (key.trim().length > 0) {
            onKeySet(key);
            try {
                if (isOR) localStorage.setItem('openrouter_model', orModel);
            } catch {}
            // Also persist to .env so backend follows the file (project follows env)
            try {
                const isORKey = key.trim().startsWith('sk-or-');
                const updates = {};
                if (isORKey) {
                    updates['OPENROUTER_API_KEY'] = key.trim();
                    updates['OPENROUTER_MODEL'] = orModel;
                } else if (key.trim().startsWith('AIza')) {
                    updates['GEMINI_API_KEY'] = key.trim();
                }
                if (Object.keys(updates).length) {
                    await fetch(getApiUrl('/api/env'), {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ updates }),
                    });
                }
            } catch {}
            setIsSaved(true);
        }
    };

    const isGemini = key.trim().startsWith('AIza');

    return (
        <div className="card p-4 sm:p-6 mb-8 animate-fade">
            <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-paper3 rounded-input text-brass">
                    <Key size={18} />
                </div>
                <div>
                    <h2 className="font-display lowercase text-lg text-ink">AI API Key</h2>
                    <p className="text-xs text-muted -mt-1">Gemini or OpenRouter (free models)</p>
                </div>
                {isOR && <span className="ml-auto px-3 py-1 rounded-full border border-brass bg-paper text-ink text-xs font-mono lowercase tracking-wide">openrouter/free</span>}
                {isGemini && <span className="ml-auto badge-ok text-xs">Gemini</span>}
            </div>

            <label htmlFor="ai-key-input" className="sr-only">AI API Key</label>
            <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative sm:flex-1">
                    <input
                        id="ai-key-input"
                        type={isVisible ? "text" : "password"}
                        value={key}
                        onChange={(e) => {
                            setKey(e.target.value);
                            setIsSaved(false);
                        }}
                        placeholder="sk-or-v1-... (OpenRouter free) or AIza... (Gemini)"
                        className="input-field pr-12 font-mono text-sm"
                        autoComplete="off"
                        spellCheck={false}
                        aria-describedby="ai-key-help"
                    />
                    <button
                        onClick={() => setIsVisible(!isVisible)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
                    >
                        {isVisible ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                </div>
                <button
                    onClick={handleSave}
                    disabled={!key || isSaved}
                    className={isSaved ? 'badge-ok px-4 cursor-default' : 'btn-primary'}
                >
                    {isSaved ? <><Check size={14} /> Ready</> : 'Set Key'}
                </button>
            </div>

            {isOR && (
                <div className="mt-3">
                    <div className="flex items-center justify-between gap-2">
                        <label htmlFor="openrouter-model-select" className="text-xs text-muted">OpenRouter model — auto-detected free ({freeModels.length})</label>
                        <button
                            type="button"
                            onClick={() => fetchFreeModels(key)}
                            disabled={loadingModels}
                            className="min-h-[32px] min-w-[44px] px-2 text-xs text-brass hover:underline flex items-center justify-center gap-1 disabled:opacity-50"
                            title="Refresh free model list from OpenRouter"
                            aria-label="Refresh model list"
                        >
                            {loadingModels ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                            {loadingModels ? 'loading...' : 'refresh'}
                        </button>
                    </div>
                    <select
                        id="openrouter-model-select"
                        value={orModel}
                        onChange={(e) => { setOrModel(e.target.value); setIsSaved(false); }}
                        className="input-field mt-1 font-mono text-sm"
                        aria-label="OpenRouter model"
                    >
                        {freeModels.map((m) => (
                            <option key={m} value={m}>{m}</option>
                        ))}
                    </select>
                    {modelsError && <p className="text-[11px] text-warn mt-1">Could not refresh: {modelsError} — showing fallback list</p>}
                    <p className="text-[11px] text-muted mt-1">Auto-detected from OpenRouter — free tier, no credit card. Pick any, saved in browser.</p>
                </div>
            )}

            <p id="ai-key-help" className="mt-3 text-xs text-muted leading-relaxed">
                Your key is stored locally in your browser (never on the server).
                {isOR ? (
                    <>
                        <br />
                        <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-brass hover:underline mt-1 inline-block">
                            Get your free OpenRouter API Key here →
                        </a>
                        <span className="mx-1">·</span>
                        <a href="https://openrouter.ai/models?max_price=0" target="_blank" rel="noopener noreferrer" className="text-brass hover:underline mt-1 inline-block">
                            Browse free models →
                        </a>
                    </>
                ) : (
                    <>
                        <br />
                        <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-brass hover:underline mt-1 inline-block">
                            Get your free Gemini API Key here →
                        </a>
                        <span className="mx-1">·</span>
                        <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-brass hover:underline mt-1 inline-block">
                            Or use OpenRouter free models →
                        </a>
                    </>
                )}
            </p>
        </div>
    );
}
