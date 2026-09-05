import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs['recommended-latest'],
    ],
    plugins: {
      "react-refresh": reactRefresh,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      // `_`-prefixed args/catches are the codebase idiom for intentionally
      // ignored values (failed localStorage, optional callbacks).
      'no-unused-vars': ['error', {
        varsIgnorePattern: '^[A-Z_]',
        argsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
      'react-refresh/only-export-components': 'warn',
    },
  },
  {
    // Node scripts: config files run outside the browser.
    files: ['*.config.js', 'vite-plugin-seo.js'],
    languageOptions: { globals: globals.node },
  },
  {
    // Entry file: route-level components live here so the hash router stays
    // readable in one place; it is never fast-refreshed as a unit.
    files: ['src/main.jsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
])
