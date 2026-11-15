import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

// Flat config written against the pinned eslint 8.57.x: the `defineConfig` /
// `globalIgnores` helpers from 'eslint/config' only exist in eslint 9, and
// eslint-plugin-react-hooks@4.x predates configs.flat, so both are inlined
// here. Rule set matches the original config, with two amendments:
//  - no-empty allows `catch {}` (every empty block in the codebase is a
//    deliberate localStorage/JSON swallow with the intent documented above it)
//  - the capitalized-identifier exemption also covers function args
//    (argsIgnorePattern), which is what the original varsIgnorePattern
//    intended for destructured component props like `icon: Icon`.
export default [
  { ignores: ['dist'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...reactRefresh.configs.vite.rules,
      'no-empty': ['error', { allowEmptyCatch: true }],
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]', argsIgnorePattern: '^[A-Z_]' }],
    },
  },
  // Build tooling runs in Node, not the browser.
  {
    files: ['vite.config.js', 'vite-plugin-seo.js', 'seo/**/*.js'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
  // Deliberate non-component exports, none of them hot-update modules:
  //  - main.jsx is the entry point (no exports by design)
  //  - AuthContext exports the useAuth hook beside the provider (standard
  //    React context shape)
  //  - WatermarkModal exports its localStorage helper for reuse.
  {
    files: [
      'src/main.jsx',
      'src/contexts/AuthContext.jsx',
      'src/components/WatermarkModal.jsx',
    ],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
]
