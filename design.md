# Design — OpenShorts

A locked design system for this app (dashboard; the runtime landing was
removed 2026-11-15 and the app is the only SPA view). Every page redesign
reads this file before emitting code. Do not regenerate per page — extend or
amend this file when the system needs to grow.

Theme: **Stark · Graphite** — the MiniMax design language, dark-only adaptation
(owner decision, 2026-11-15). Register: stark AI-infrastructure editorial
(MiniMax school): neutral near-black canvas, near-white ink, hairline flat
cards, pill CTAs. The product's own numbers — timecodes, aspect ratios, clip
counts, costs — are the decoration: they render as UPPERCASE mono readouts.

## Genre

stark

## Macrostructure family

- Marketing pages: none at runtime. The build still emits static SEO pages
  (vite-plugin-seo.js) served by nginx; they are separate documents, not views.
- App pages (dashboard tabs, modals — the only SPA view): **Workbench** — small functional
  headings, hairline flat cards, mono readouts, zero enrichment.
  Function carries the page.
- Content pages (Legal): **Long Document** — single column, 65ch measure,
  inline headings, typographic links.

## Theme tokens (Stark · Graphite)

- `--color-paper`      oklch(14% 0 0)        — page canvas, neutral graphite (no hue)
- `--color-paper-2`    oklch(18.5% 0 0)      — elevated surface (cards, modals, sidebar)
- `--color-paper-3`    oklch(23% 0 0)        — hover surface / inset chips
- `--color-ink`        oklch(97% 0 0)        — headlines, near-white
- `--color-ink-2`      oklch(88% 0 0)        — body text
- `--color-muted`      oklch(62% 0 0)        — secondary text
- `--color-rule`       oklch(97% 0 0 / 0.10) — hairline borders
- `--color-rule-2`     oklch(97% 0 0 / 0.16) — stronger hairline
- `--rule-blueprint`   oklch(97% 0 0 / 0.05) — scanner grid (ProcessingAnimation only)
- `--color-accent`     oklch(97% 0 0)        — the accent IS ink: primary CTAs are white pills
- `--color-accent-ink` oklch(13% 0 0)        — label on ink fills (near-black)
- `--color-accent-2`   oklch(66% 0.19 27)    — brand coral (identity moments ONLY)
- `--color-glow`       oklch(97% 0 0 / 0.10) — scanner halo (ProcessingAnimation only)
- `--color-paper-emit` oklch(97% 0 0 / 0.03) — scanner overlay wash
- `--color-focus`      oklch(70% 0.13 255)   — focus rings + form activation (electric blue)
- `--color-ok`         oklch(76% 0.12 150)   — success states
- `--color-warn`       oklch(80% 0.13 80)    — warnings (keys missing, low quota)
- `--color-danger`     oklch(68% 0.17 25)    — errors, destructive
- Product-identity encodings, RESERVED (tokens only, no Tailwind mapping):
  `--color-brand-coral` oklch(66% 0.19 27) · `--color-brand-magenta` oklch(68% 0.19 335)
  · `--color-brand-blue` oklch(62% 0.16 260) · `--color-brand-cyan` oklch(80% 0.12 220)
  · `--color-brand-purple` oklch(65% 0.19 295) · `--color-brand-orange` oklch(74% 0.15 55)

Tailwind names: `paper, paper2, paper3, ink, ink2, muted, brass, brassink,
coral, ok, warn, danger` (+ legacy aliases `background→paper`, `surface→paper2`,
`primary→brass`, `accent→coral`). **Read names semantically, not literally**:
`brass`/`primary` render the ink-fill (white pill) since the MiniMax dark
adaptation; `coral`/`accent` render brand coral. Borders: use `border-rule` /
`border-rule2` utilities.

## Typography

Instrument Serif, Geist and Sora are retired (owner decisions, 2026-11-15).
**DM Sans** is the single UI typeface, for display and body alike (MiniMax
school: one face, every role). Inter is the declared fallback, never loaded.
No italic variant exists in the deployment — emphasis comes from weight
(400 body / 500 medium / 600 headings+buttons / 700 strong inline only).

- Display: **DM Sans 600**, `font-display`, always roman (never italic),
  **lowercase**, tracking -0.02em, line-height 1.10 (MiniMax hero leading).
- Body: **DM Sans** 400/500, `font-body`, line-height 1.5; long-form
  captions may run 1.7 (docs register).
- Mono: **JetBrains Mono** 400/500, `font-mono` — UPPERCASE labels only.
- Two-register rule: UI prose (headings, buttons, nav, empty states, helper
  text) renders **lowercase**; mono labels (eyebrows, badges, readouts, stat
  labels, keyboard hints) render **UPPERCASE** 10.5–11px tracking 0.10em at
  ~55% opacity. That contrast is the typographic signature.
- **NEVER lowercase user content**: video titles, captions, transcripts,
  descriptions, emails, API keys, log output, filenames, prices in legal copy.
  Apply `lowercase` class per-element on UI chrome only — no global
  text-transform on body.
- Numerals: `font-variant-numeric: tabular-nums` wherever numbers appear
  (`tabular-nums` utility). Big stats: DM Sans 600 + tabular-nums.
App headings stay small: text-xl/2xl max, DM Sans lowercase (weight 600). No
display-size scale exists; the landing hero that owned `--text-display` is
retired with the landing.

## Spacing

4-point scale via Tailwind defaults (p-2/3/4/6/8/12/16). No arbitrary
`text-[9px]`-style values — minimum readable label is 10.5px (`text-micro`
utility). Radii (MiniMax scale): `--radius-card: 12px` (rounded-card,
docs-register), `--radius-input: 8px` (rounded-input), `--radius-feature:
32px` (reserved for featured identity panels), pills `rounded-full` for every
button, chip and badge — a non-pill button signals "third-party widget".

## Motion

- Easings: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)` only. Never `ease`.
- Durations: 180ms UI state (MiniMax recommendation: 150–200ms), 600ms
  section reveals, 4s scanner pulse.
- Reveal pattern: fade only (`animate-fade`), optional 12px translateY on
  section entry. No slide-ins, no bounce, no scale-pops.
- Cards hover: `translateY(-2px)` + border brightens, 180ms. Elevation is
  the border, never a shadow, except modals/sticky panels.
- Reduced motion: everything collapses to instant final state.
- Focus ring: 2px electric blue, appears INSTANTLY (never animated).

## Microinteractions stance

- Silent success (inline check, quiet state change) — never celebratory.
- Buttons: `active:translate-y-px`, no scale tricks.
- Hover tooltips delay 800ms; focus tooltips 0ms.
- Loaders: `Loader2` lucide spin is fine, tinted `text-muted` or `text-ink`.

## CTA voice

- Primary: `.btn-primary` — ink fill (white pill), `text-brassink`
  (near-black label), `rounded-full`, lowercase label, font-medium. One per
  view section. Rest = near-white; pressed lifts to charcoal (brightness 0.88).
- Secondary: `.btn-ghost` — outline pill, 1px ink at 55% → full ink on hover,
  ink text, rounded-full.
- Tertiary/utility: `.btn-quiet` — `bg-paper3` fill, no border.
- Destructive: `.btn-danger` — danger outline, fills on hover.
- Labels are verbs, lowercase: "start clipping", "generate", "publish",
  "download". Never "Get Started!", never Title Case.

## Component recipes (shared — use these, don't reinvent)

- `.card` — flat hairline card: bg-paper2 + 1px rule, rounded-card, no
  emission, no shadow. Hover variant `.card-hover` lifts -2px and brightens
  the border. Replaces ALL glass-panel / bg-surface/50 / backdrop-blur cards.
- `.eyebrow` — mono UPPERCASE micro label. Section pattern: eyebrow stacked
  ABOVE the heading, same column (`01 · TOOLS` then the heading). Never
  tag-left/heading-right.
- `<Modal>` from `src/components/ui/Modal.jsx` — the ONLY modal shell
  (overlay plain `bg-black/70`, NO backdrop-blur; panel bg-paper2 hairline).
- `<SegmentedControl>` from `src/components/ui/SegmentedControl.jsx` — all
  option-button grids (position/size/animation pickers, platform toggles).
  Active state = paper3 fill + rule2 hairline + ink text. Never bg-white
  text-black, never per-feature colors.
- `<StepIndicator>` from `src/components/ui/StepIndicator.jsx` — the single
  wizard stepper (ThumbnailStudio + SaaShortsTab share it). Mono ordinals.
- `.input-field` — inset bg-paper, hairline, focus electric-blue border
  (redefined in index.css; existing class name kept).
- `.readout` — mono UPPERCASE value chip for machine data (timecodes, costs,
  ratios, model names): `00:42 · 9:16 · $0.65`.
- Status: `.badge-ok` / `.badge-warn` / `.badge-danger` — tinted 10% fills,
  mono uppercase. `.badge-brass` renders as the ink chip; coral badges are
  reserved for NEW / live / record-identity moments only.

## What pages MUST share

- Single accent: the ink-fill (white pill). Coral at most one small identity
  highlight per view (NEW badge, live marker). NOTHING ELSE gets a hue.
- Zero gradients (text or background). Zero glassmorphism / backdrop-blur
  panels. Zero per-feature identity colors (the old violet/emerald/amber/teal
  per-tab coding is retired — tools are differentiated by mono eyebrow ordinals
  `01 · CLIPS`, `02 · AI SHORTS`, not by hue).
- The two-register typography (lowercase prose / UPPERCASE mono labels).
- The CTA voice, radii, hairline flat-card language.
- English copy everywhere (ScheduleWeekModal migrates from Spanish).
- Lucide icons at 16–18px, `text-muted` default, ink when active.

## What pages MAY differ on

- App pages get NO enrichment (no grid bg, no apparatus, no meter) — except
  ProcessingAnimation, which keeps its scanner HUD re-tinted to neutral
  tokens (blueprint grid + white scanline). The landing apparatus was
  retired with the landing (2026-11-15).
- Legal is typography-only.

## Hard bans (Stark · Graphite)

No italics anywhere. No gradient text. No gradient buttons. No backdrop-blur.
No glowing orbs, no radial card emission, no halos — the scanner HUD is the
one sanctioned exception. No heavy shadows on cards; flat-with-hairline is
the default (modals/sticky panels only). No invented metrics (existing cited
stats/prices are the brief's real copy — keep them). No emoji as icons in
chrome (existing emoji option labels in SaaShorts pickers may stay as
content). No `bg-[#121214]`-style hardcoded colors — tokens only. No Title
Case UI copy. Brand colors (coral/magenta/blue/cyan/purple/orange) never on
generic buttons, body text or large surfaces — they earn a surface only when
the surface IS the product.

## Functional contract (NEVER break)

Hash routing (`#app`, `#/pricing`, `#/account`, `#legal`; old `#landing` and
section anchors resolve to the app), `billingEnabled` /
`isManaged` / `isSignedIn` gating, all handlers and props, localStorage keys
(`gemini_key`, `uploadPostKey_v3`, `elevenLabsKey_v1`, `falKey_v1`,
`uploadUserId`, `openshorts_session`, `openshorts_auth`), API calls and BYOK
headers, QuotaError flows,
Remotion preview/render wiring. Redesign is classes + markup structure only.
