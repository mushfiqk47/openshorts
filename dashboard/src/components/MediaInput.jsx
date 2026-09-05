import React, { useState, useEffect, useRef } from 'react';
import { Link2, Upload, FileVideo, X, Info, Loader2, ChevronDown } from 'lucide-react';
import { getApiUrl } from '../config';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import {
  Select,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectItem,
} from './ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';

const SUPPORTED_PLATFORMS = [
    'YouTube', 'Vimeo', 'TikTok', 'X / Twitter', 'Twitch',
    'Facebook', 'Instagram', 'Dailymotion', 'Reddit', 'Streamable',
];

const HOOK_STYLES = [
    { value: 'classic', label: 'Classic' },
    { value: 'dark', label: 'Dark' },
    { value: 'yellow', label: 'Yellow' },
    { value: 'red', label: 'Red' },
    { value: 'outline', label: 'Outline' },
    { value: 'outline_yellow', label: 'Outline+' },
];

export default function MediaInput({ onProcess, isProcessing }) {
    const [youtubeUrlEnabled, setYoutubeUrlEnabled] = useState(true);
    // File upload is the primary path; the link is secondary.
    const [mode, setMode] = useState('file'); // 'file' | 'url'
    const [url, setUrl] = useState('');
    const [file, setFile] = useState(null);
    // User-supplied transcript (Whisper removed): required, .srt/.vtt/.txt/.md/.json.
    const [transcriptFile, setTranscriptFile] = useState(null);
    const [outputFormat, setOutputFormat] = useState('vertical'); // vertical | horizontal | square
    const [showInfo, setShowInfo] = useState(false);
    // Advanced generation controls — empty string means "let the AI decide",
    // which keeps the default pipeline behavior untouched.
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [targetClips, setTargetClips] = useState('');
    const [clipMinSeconds, setClipMinSeconds] = useState('');
    const [clipMaxSeconds, setClipMaxSeconds] = useState('');
    // Auto-hook: burn the AI hook text into every clip. On by default; the
    // choice persists so turning it off sticks across sessions.
    const [autoHook, setAutoHook] = useState(() => {
        try { return localStorage.getItem('os_auto_hook') !== '0'; } catch { return true; }
    });
    const [autoHookStyle, setAutoHookStyle] = useState(() => {
        try { return localStorage.getItem('os_auto_hook_style') || 'classic'; } catch { return 'classic'; }
    });
    // Drag-over highlight: dragover fires continuously, so track entry depth
    // to avoid flicker when crossing child elements.
    const [dragDepth, setDragDepth] = useState(0);
    const isDragging = dragDepth > 0;
    const infoRef = useRef(null);

    // Close the compatibility popover on any outside click.
    useEffect(() => {
        if (!showInfo) return;
        const onClick = (e) => {
            if (infoRef.current && !infoRef.current.contains(e.target)) setShowInfo(false);
        };
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, [showInfo]);

    useEffect(() => {
        fetch(getApiUrl('/api/config'))
            .then((r) => r.ok ? r.json() : null)
            .then((cfg) => {
                if (cfg && cfg.youtubeUrlEnabled === false) {
                    setYoutubeUrlEnabled(false);
                    setMode('file');
                }
            })
            .catch(() => {});
    }, []);

    // A link pasted in the landing hero: preload it here so the user picks up
    // where they left off. Not auto-submitted — the rights attestation below
    // has to be ticked by the user.
    useEffect(() => {
        let pending = null;
        try {
            pending = localStorage.getItem('os_pending_url');
            if (pending) localStorage.removeItem('os_pending_url');
        } catch { /* ignore */ }
        if (pending) {
            setMode('url');
            setUrl(pending);
        }
    }, []);

    const handleSubmit = (e) => {
        e.preventDefault();
        // Local single-user tool: attestation removed, acknowledged is always true.
        const advanced = {
            targetClips: targetClips || null,
            clipMinSeconds: clipMinSeconds || null,
            clipMaxSeconds: clipMaxSeconds || null,
            autoHook,
            autoHookStyle,
        };
        try {
            localStorage.setItem('os_auto_hook', autoHook ? '1' : '0');
            localStorage.setItem('os_auto_hook_style', autoHookStyle);
        } catch { /* ignore */ }
        if (mode === 'url' && url) {
            onProcess({ type: 'url', payload: url, acknowledged: true, outputFormat, transcriptFile, ...advanced });
        } else if (mode === 'file' && file) {
            onProcess({ type: 'file', payload: file, acknowledged: true, outputFormat, transcriptFile, ...advanced });
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragDepth(0);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setMode('file');
        }
    };

    const canSubmit = !isProcessing && transcriptFile && (
        (mode === 'url' && url) || (mode === 'file' && file)
    );

    return (
        <div className="card p-4 sm:p-6 animate-fade">
            <Tabs value={mode} onValueChange={setMode}>
                <TabsList aria-label="input source" className="mb-6 w-full justify-start">
                    <TabsTrigger value="file" className="data-[state=active]:[&_svg]:text-brass">
                        <Upload aria-hidden="true" />
                        Upload File
                    </TabsTrigger>
                    {youtubeUrlEnabled && (
                        <TabsTrigger value="url" className="data-[state=active]:[&_svg]:text-brass">
                            <Link2 aria-hidden="true" />
                            Video URL
                        </TabsTrigger>
                    )}
                </TabsList>

                <form onSubmit={handleSubmit}>
                    <TabsContent value="url">
                        <div className="relative">
                            <Input
                                type="url"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                placeholder="https://... paste a video link"
                                required={mode === 'url'}
                                className="pr-11"
                            />
                            <div className="absolute inset-y-0 right-2 flex items-center" ref={infoRef}>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setShowInfo((v) => !v)}
                                    aria-label="Supported platforms"
                                    aria-expanded={showInfo}
                                    aria-controls="platform-info-popover"
                                >
                                    <Info size={16} />
                                </Button>
                                {showInfo && (
                                    <div id="platform-info-popover" className="absolute right-0 top-full mt-2 w-64 z-20 card p-4 text-left animate-fade">
                                        <p className="eyebrow mb-2">Paste a link from</p>
                                        <div className="flex flex-wrap gap-1.5">
                                            {SUPPORTED_PLATFORMS.map((p) => (
                                                <span key={p} className="text-xs px-2 py-0.5 rounded-full bg-paper3 text-ink2">
                                                    {p}
                                                </span>
                                            ))}
                                        </div>
                                        <p className="text-xs text-muted mt-2.5 leading-relaxed">
                                            …and 1,000+ more sites. If a link has a public video, we can usually fetch it.
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </TabsContent>

                    <TabsContent value="file">
                        <div
                            className={`border-2 border-dashed rounded-card p-6 sm:p-8 text-center transition-colors focus-within:border-brass ${file ? 'border-brass' : isDragging ? 'border-brass bg-paper3' : 'border-rule2 hover:border-brass'}`}
                            onDragEnter={(e) => { e.preventDefault(); setDragDepth((d) => d + 1); }}
                            onDragOver={(e) => e.preventDefault()}
                            onDragLeave={(e) => { e.preventDefault(); setDragDepth((d) => Math.max(0, d - 1)); }}
                            onDrop={handleDrop}
                        >
                            {file ? (
                                <div className="flex items-center justify-center gap-3 text-ok min-w-0">
                                    <FileVideo size={18} className="shrink-0" aria-hidden="true" />
                                    <span className="font-medium truncate">{file.name}</span>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => setFile(null)}
                                        aria-label="remove selected file"
                                    >
                                        <X size={16} />
                                    </Button>
                                </div>
                            ) : (
                                <Label htmlFor="clip-file-input" className="block normal-case">
                                    <Input
                                        id="clip-file-input"
                                        type="file"
                                        accept="video/*"
                                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                                        aria-describedby="upload-hint"
                                        className="sr-only"
                                    />
                                    <Upload className="mx-auto mb-3 text-muted" size={18} aria-hidden="true" />
                                    <span className="block text-sm text-ink2">
                                        Click to upload or drag and drop{isDragging ? ' — drop to add' : ''}
                                    </span>
                                    <span id="upload-hint" className="readout mt-2 block">MP4, MOV up to 2GB</span>
                                </Label>
                            )}
                        </div>
                    </TabsContent>

                    {/* Transcript file — required (no auto-transcription) */}
                    <div className="mt-4">
                        <Label htmlFor="clip-transcript-input" className="mb-1.5 block">transcript file · required</Label>
                        <div className={`border-2 border-dashed rounded-card p-4 text-center transition-colors focus-within:border-brass ${transcriptFile ? 'border-brass' : 'border-rule2 hover:border-brass'}`}>
                            {transcriptFile ? (
                                <div className="flex items-center justify-center gap-3 text-ok min-w-0">
                                    <FileVideo size={18} className="shrink-0" aria-hidden="true" />
                                    <span className="font-medium truncate">{transcriptFile.name}</span>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => setTranscriptFile(null)}
                                        aria-label="remove transcript file"
                                    >
                                        <X size={16} />
                                    </Button>
                                </div>
                            ) : (
                                <Label htmlFor="clip-transcript-input" className="block normal-case cursor-pointer">
                                    <Input
                                        id="clip-transcript-input"
                                        type="file"
                                        accept=".srt,.vtt,.txt,.md,.markdown,.json"
                                        onChange={(e) => setTranscriptFile(e.target.files?.[0] || null)}
                                        aria-describedby="transcript-hint"
                                        className="sr-only"
                                    />
                                    <Upload className="mx-auto mb-2 text-muted" size={18} aria-hidden="true" />
                                    <span className="block text-sm text-ink2">Click to add the transcript</span>
                                    <span id="transcript-hint" className="readout mt-2 block">SRT, VTT, TXT, MD or JSON · max 5MB</span>
                                </Label>
                            )}
                        </div>
                    </div>

                    {/* Output format selector */}
                    <div className="mt-5">
                        <p className="eyebrow mb-2" id="output-format-label">Output format</p>
                        <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-labelledby="output-format-label">
                            {[
                                { value: 'vertical', label: '9:16', hint: 'Shorts · Reels · TikTok', w: 18, h: 32 },
                                { value: 'square', label: '1:1', hint: 'Feed posts', w: 28, h: 28 },
                                { value: 'horizontal', label: '16:9', hint: 'Keep landscape · YouTube', w: 36, h: 20 },
                            ].map((f) => {
                                const active = outputFormat === f.value;
                                return (
                                    <button
                                        key={f.value}
                                        type="button"
                                        role="radio"
                                        aria-checked={active}
                                        onClick={() => setOutputFormat(f.value)}
                                        className={`py-3 px-2 rounded-input border flex flex-col items-center gap-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass
                                            ${active ? 'border-brass text-ink' : 'border-rule2 text-muted hover:border-brass'}`}
                                    >
                                        <span
                                            aria-hidden="true"
                                            className="rounded-[3px] border-2 transition-colors"
                                            style={{
                                                width: `${f.w}px`,
                                                height: `${f.h}px`,
                                                borderColor: active ? 'var(--color-accent)' : 'var(--color-rule-2)',
                                                backgroundColor: active ? 'color-mix(in srgb, var(--color-accent) 22%, transparent)' : 'transparent',
                                            }}
                                        />
                                        <span className="block font-mono text-sm leading-none">{f.label}</span>
                                        <span className="block text-[10px] leading-tight text-center text-muted">{f.hint}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Advanced generation controls — collapsed by default; blank = AI decides */}
                    <div className="mt-4">
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowAdvanced((v) => !v)}
                            aria-expanded={showAdvanced}
                            aria-controls="advanced-options"
                            className="text-muted hover:text-ink2"
                        >
                            <ChevronDown size={14} className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                            advanced options
                            {(targetClips || clipMinSeconds || clipMaxSeconds || !autoHook) && (
                                <span className="text-brass" aria-hidden="true">·</span>
                            )}
                        </Button>
                        {showAdvanced && (
                            <div id="advanced-options" className="mt-3 grid grid-cols-3 gap-2 animate-fade">
                                <div className="space-y-1.5">
                                    <Label htmlFor="target-clips">clips to aim for</Label>
                                    <Input
                                        id="target-clips"
                                        type="number" min="1" max="15" step="1"
                                        value={targetClips}
                                        onChange={(e) => setTargetClips(e.target.value)}
                                        placeholder="auto"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <Label htmlFor="clip-min">min length (s)</Label>
                                    <Input
                                        id="clip-min"
                                        type="number" min="5" max="175" step="1"
                                        value={clipMinSeconds}
                                        onChange={(e) => setClipMinSeconds(e.target.value)}
                                        placeholder="15"
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <Label htmlFor="clip-max">max length (s)</Label>
                                    <Input
                                        id="clip-max"
                                        type="number" min="10" max="180" step="1"
                                        value={clipMaxSeconds}
                                        onChange={(e) => setClipMaxSeconds(e.target.value)}
                                        placeholder="60"
                                    />
                                </div>
                                <p className="col-span-3 text-[11px] leading-relaxed text-muted">
                                    Targets, not guarantees: the AI returns fewer clips when the
                                    material doesn't hold them. Leave blank to let it decide.
                                </p>
                                <div className="col-span-3 flex items-center justify-between gap-3 pt-1 border-t border-rule">
                                    <div className="flex items-center gap-2">
                                        <Checkbox
                                            id="auto-hook"
                                            checked={autoHook}
                                            onCheckedChange={(v) => setAutoHook(v === true)}
                                        />
                                        <Label htmlFor="auto-hook" className="normal-case text-xs text-ink2 opacity-100 cursor-pointer">
                                            auto hook titles on clips
                                        </Label>
                                    </div>
                                    {autoHook && (
                                        <Select value={autoHookStyle} onValueChange={setAutoHookStyle}>
                                            <SelectTrigger className="w-auto text-xs" aria-label="hook style">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {HOOK_STYLES.map((s) => (
                                                    <SelectItem key={s.value} value={s.value}>
                                                        {s.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    <Button
                        type="submit"
                        disabled={!canSubmit}
                        className="w-full mt-4"
                    >
                        {isProcessing && <Loader2 size={16} className="animate-spin" />}
                        {isProcessing ? 'Processing Video...' : 'Generate Clips'}
                    </Button>
                </form>
            </Tabs>
        </div>
    );
}
