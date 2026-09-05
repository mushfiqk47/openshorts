import React, { useState, useEffect } from 'react';
import { Cpu, Eye, EyeOff, Check, RefreshCw, Loader2, Server, Key, AlertCircle } from 'lucide-react';
import { getApiUrl } from '../config';

const DEFAULT_BASE_URL = 'http://localhost:11434/v1';
const DEFAULT_MODEL = 'llama3.2:1b';

export default function KeyInput({ onKeySet, savedKey }) {
    const [provider, setProvider] = useState(() => {
        try { return localStorage.getItem('llm_provider') || 'ollama'; } catch { return 'ollama'; }
    });
    const [baseUrl, setBaseUrl] = useState(() => {
        try { return localStorage.getItem('llm_base_url') || DEFAULT_BASE_URL; } catch { return DEFAULT_BASE_URL; }
    });
    const [model, setModel] = useState(() => {
        try { return localStorage.getItem('llm_model') || DEFAULT_MODEL; } catch { return DEFAULT_MODEL; }
    });
    const [apiKey, setApiKey] = useState(() => {
        try { return savedKey || localStorage.getItem('llm_api_key') || ''; } catch { return savedKey || ''; }
    });
    const [availableModels, setAvailableModels] = useState([]);
    const [loadingModels, setLoadingModels] = useState(false);
    const [modelsError, setModelsError] = useState(null);
    const [isVisible, setIsVisible] = useState(false);
    const [isSaved, setIsSaved] = useState(false);
    const [isCustomModel, setIsCustomModel] = useState(false);

    const fetchModels = async (targetUrl = baseUrl, targetKey = apiKey) => {
        if (provider === 'gemini') return;
        setLoadingModels(true);
        setModelsError(null);
        try {
            const url = `${getApiUrl('/api/llm/models')}?base_url=${encodeURIComponent(targetUrl)}`;
            const headers = {};
            if (targetKey && targetKey.trim()) {
                headers['X-LLM-Key'] = targetKey.trim();
            }
            const res = await fetch(url, { headers });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            const list = data.models || [];
            const ids = list.map(m => m.id).filter(Boolean);
            setAvailableModels(ids);
            if (ids.length > 0) {
                if (!ids.includes(model) && !isCustomModel) {
                    // Pick matching model or first available
                    const matched = ids.find(id => id.includes('llama') || id.includes('qwen') || id.includes('mistral')) || ids[0];
                    setModel(matched);
                    try { localStorage.setItem('llm_model', matched); } catch { /* ignore */ }
                }
            } else if (data.warning) {
                setModelsError(data.warning);
            }
        } catch (e) {
            setModelsError(e.message || 'Could not connect to LLM server');
        } finally {
            setLoadingModels(false);
        }
    };

    useEffect(() => {
        if (provider !== 'gemini') {
            fetchModels(baseUrl, apiKey);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [provider, baseUrl]);

    useEffect(() => {
        if (savedKey && provider === 'gemini') {
            setApiKey(savedKey);
        }
    }, [savedKey, provider]);

    const handleSave = async () => {
        setIsSaved(false);
        try {
            localStorage.setItem('llm_provider', provider);
            localStorage.setItem('llm_base_url', baseUrl);
            localStorage.setItem('llm_model', model);
            localStorage.setItem('llm_api_key', apiKey);
            localStorage.setItem('os_ai_key', apiKey || (provider === 'ollama' ? 'ollama' : ''));
        } catch { /* ignore */ }

        // Persist directly to .env on the server
        try {
            const updates = {
                LLM_PROVIDER: provider,
            };
            if (provider === 'gemini') {
                updates.GEMINI_API_KEY = apiKey.trim();
            } else {
                updates.LLM_BASE_URL = baseUrl.trim();
                updates.LLM_MODEL = model.trim();
                if (apiKey.trim()) {
                    updates.LLM_API_KEY = apiKey.trim();
                } else if (provider === 'ollama') {
                    updates.LLM_API_KEY = 'ollama';
                }
            }
            await fetch(getApiUrl('/api/env'), {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ updates }),
            });
        } catch (e) {
            console.error('Failed to update .env', e);
        }

        if (onKeySet) {
            onKeySet(apiKey || (provider === 'ollama' ? 'ollama' : 'ready'));
        }
        setIsSaved(true);
    };

    return (
        <div className="card p-4 sm:p-6 mb-8 animate-fade">
            <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-paper3 rounded-input text-brass">
                    <Cpu size={18} />
                </div>
                <div>
                    <h2 className="font-display lowercase text-lg text-ink">AI Model & Provider</h2>
                    <p className="text-xs text-muted -mt-1">Local Ollama (default), OpenAI-compatible, or Gemini</p>
                </div>
                {provider === 'ollama' && (
                    <span className="ml-auto px-3 py-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-mono lowercase tracking-wide flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        ollama (local)
                    </span>
                )}
                {provider === 'openai_compatible' && (
                    <span className="ml-auto px-3 py-1 rounded-full border border-brass/30 bg-brass/10 text-brass text-xs font-mono lowercase tracking-wide">
                        openai-compatible
                    </span>
                )}
                {provider === 'gemini' && (
                    <span className="ml-auto badge-ok text-xs">
                        gemini
                    </span>
                )}
            </div>

            {/* Provider Tabs */}
            <div className="flex gap-2 p-1 bg-paper2 rounded-lg mb-4 text-xs">
                <button
                    type="button"
                    onClick={() => { setProvider('ollama'); setBaseUrl(DEFAULT_BASE_URL); setIsSaved(false); }}
                    className={`flex-1 py-1.5 px-3 rounded-md font-medium transition-all ${
                        provider === 'ollama'
                            ? 'bg-paper text-ink shadow-sm border border-rule'
                            : 'text-muted hover:text-ink'
                    }`}
                >
                    Ollama (Local Default)
                </button>
                <button
                    type="button"
                    onClick={() => { setProvider('openai_compatible'); setIsSaved(false); }}
                    className={`flex-1 py-1.5 px-3 rounded-md font-medium transition-all ${
                        provider === 'openai_compatible'
                            ? 'bg-paper text-ink shadow-sm border border-rule'
                            : 'text-muted hover:text-ink'
                    }`}
                >
                    OpenAI-Compatible
                </button>
                <button
                    type="button"
                    onClick={() => { setProvider('gemini'); setIsSaved(false); }}
                    className={`flex-1 py-1.5 px-3 rounded-md font-medium transition-all ${
                        provider === 'gemini'
                            ? 'bg-paper text-ink shadow-sm border border-rule'
                            : 'text-muted hover:text-ink'
                    }`}
                >
                    Gemini
                </button>
            </div>

            {/* Ollama & OpenAI-Compatible settings */}
            {provider !== 'gemini' ? (
                <div className="space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs text-muted block mb-1">Base URL</label>
                            <input
                                type="text"
                                value={baseUrl}
                                onChange={(e) => { setBaseUrl(e.target.value); setIsSaved(false); }}
                                placeholder={DEFAULT_BASE_URL}
                                className="input-field font-mono text-sm"
                                spellCheck={false}
                            />
                        </div>
                        <div>
                            <div className="flex items-center justify-between gap-2 mb-1">
                                <label className="text-xs text-muted">Model Name</label>
                                <div className="flex items-center gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setIsCustomModel(!isCustomModel)}
                                        className="text-[11px] text-muted hover:text-ink underline"
                                    >
                                        {isCustomModel ? 'select list' : 'custom name'}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => fetchModels(baseUrl, apiKey)}
                                        disabled={loadingModels}
                                        className="text-[11px] text-brass hover:underline flex items-center gap-1 disabled:opacity-50"
                                        title="Refresh models from endpoint"
                                    >
                                        {loadingModels ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                                        refresh
                                    </button>
                                </div>
                            </div>
                            {isCustomModel || availableModels.length === 0 ? (
                                <input
                                    type="text"
                                    value={model}
                                    onChange={(e) => { setModel(e.target.value); setIsSaved(false); }}
                                    placeholder="llama3.2:1b"
                                    className="input-field font-mono text-sm"
                                    spellCheck={false}
                                />
                            ) : (
                                <select
                                    value={model}
                                    onChange={(e) => { setModel(e.target.value); setIsSaved(false); }}
                                    className="input-field font-mono text-sm"
                                >
                                    {availableModels.map((m) => (
                                        <option key={m} value={m}>{m}</option>
                                    ))}
                                </select>
                            )}
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-muted block mb-1">
                            {provider === 'ollama' ? 'API Key (Optional for Ollama)' : 'API Key (Bearer token)'}
                        </label>
                        <div className="relative">
                            <input
                                type={isVisible ? 'text' : 'password'}
                                value={apiKey}
                                onChange={(e) => { setApiKey(e.target.value); setIsSaved(false); }}
                                placeholder={provider === 'ollama' ? 'ollama (not required for local)' : 'sk-...'}
                                className="input-field pr-12 font-mono text-sm"
                                autoComplete="off"
                                spellCheck={false}
                            />
                            <button
                                type="button"
                                onClick={() => setIsVisible(!isVisible)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
                            >
                                {isVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </div>

                    {modelsError && (
                        <div className="flex items-start gap-2 p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-md text-amber-400 text-xs mt-2">
                            <AlertCircle size={14} className="shrink-0 mt-0.5" />
                            <div>
                                <span className="font-semibold">Endpoint status:</span> {modelsError}
                                {provider === 'ollama' && (
                                    <p className="mt-1 text-muted text-[11px]">
                                        Make sure Ollama is running in the background: run <code className="text-brass">ollama serve</code> or <code className="text-brass">ollama run llama3.2:1b</code> in terminal.
                                    </p>
                                )}
                            </div>
                        </div>
                    )}

                    {availableModels.length > 0 && (
                        <p className="text-[11px] text-emerald-400/80 flex items-center gap-1.5 mt-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                            Connected to {baseUrl} — {availableModels.length} model(s) available
                        </p>
                    )}
                </div>
            ) : (
                /* Gemini mode */
                <div>
                    <label className="text-xs text-muted block mb-1">Gemini API Key</label>
                    <div className="relative">
                        <input
                            type={isVisible ? 'text' : 'password'}
                            value={apiKey}
                            onChange={(e) => { setApiKey(e.target.value); setIsSaved(false); }}
                            placeholder="AIzaSy..."
                            className="input-field pr-12 font-mono text-sm"
                            autoComplete="off"
                            spellCheck={false}
                        />
                        <button
                            type="button"
                            onClick={() => setIsVisible(!isVisible)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ink transition-colors"
                        >
                            {isVisible ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                    </div>
                    <p className="text-xs text-muted mt-2">
                        <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-brass hover:underline">
                            Get your Gemini API Key from Google AI Studio →
                        </a>
                    </p>
                </div>
            )}

            <div className="flex items-center justify-between gap-3 mt-4 pt-3 border-t border-rule">
                <p className="text-xs text-muted">
                    Saved settings take effect immediately across all generation jobs.
                </p>
                <button
                    type="button"
                    onClick={handleSave}
                    className={isSaved ? 'badge-ok px-4 py-2 cursor-default' : 'btn-primary px-4 py-2 text-xs'}
                >
                    {isSaved ? <><Check size={14} /> Ready</> : 'Save Settings'}
                </button>
            </div>
        </div>
    );
}
