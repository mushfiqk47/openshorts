/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Stark · graphite (MiniMax dark) — values mirror tokens.css (kept
        // literal so Tailwind alpha modifiers like bg-brass/10 compile).
        // NOTE: "brass"/"primary" are legacy utility names that now render the
        // ink-fill (white pill); "coral" is the reserved identity accent.
        paper: "oklch(14% 0 0 / <alpha-value>)",
        paper2: "oklch(18.5% 0 0 / <alpha-value>)",
        paper3: "oklch(23% 0 0 / <alpha-value>)",
        ink: "oklch(97% 0 0 / <alpha-value>)",
        ink2: "oklch(88% 0 0 / <alpha-value>)",
        muted: "oklch(62% 0 0 / <alpha-value>)",
        brass: "oklch(97% 0 0 / <alpha-value>)",
        brassink: "oklch(13% 0 0 / <alpha-value>)",
        coral: "oklch(66% 0.19 27 / <alpha-value>)",
        ok: "oklch(76% 0.12 150 / <alpha-value>)",
        warn: "oklch(80% 0.13 80 / <alpha-value>)",
        danger: "oklch(68% 0.17 25 / <alpha-value>)",
        // legacy aliases so untouched files degrade gracefully
        background: "oklch(14% 0 0 / <alpha-value>)",
        surface: "oklch(18.5% 0 0 / <alpha-value>)",
        primary: "oklch(97% 0 0 / <alpha-value>)",
        accent: "oklch(66% 0.19 27 / <alpha-value>)",
      },
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        sans: "var(--font-body)",
        serif: "var(--font-display)",
        mono: "var(--font-mono)",
      },
      borderColor: {
        rule: "var(--color-rule)",
        rule2: "var(--color-rule-2)",
      },
      borderRadius: {
        card: "var(--radius-card)",
        input: "var(--radius-input)",
      },
      fontSize: {
        micro: ["10.5px", { letterSpacing: "0.10em" }],
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade': 'fadeIn 0.4s var(--ease-out)',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
