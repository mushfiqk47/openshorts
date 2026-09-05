import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import seo from './vite-plugin-seo'

// Backend target for the dev proxy. Defaults to localhost so plain
// `npm run dev` works against `python main.py` with no extra env.
// Docker compose overrides via VITE_PROXY_TARGET=http://backend:8000.
const backend = (process.env.VITE_PROXY_TARGET || 'http://localhost:8000').trim()
const renderer = (process.env.VITE_RENDER_TARGET || 'http://localhost:3100').trim()

// https://vitejs.dev/config/
export default defineConfig({
  // seo() runs on build only. It injects the crawler-visible homepage content
  // into #root and emits the static /alternatives pages, sitemap.xml and
  // llms.txt. See vite-plugin-seo.js.
  plugins: [react(), seo()],
  server: {
    port: 5173,
    strictPort: true,
    // Never watch build output or media: a locked .mp4 under dist/ crashes
    // the dev server on Windows with EBUSY (chokidar cannot watch it).
    watch: { ignored: ['**/dist/**', '**/node_modules/**', '**/*.mp4'] },
    allowedHosts: [
      'openshorts.app',
      'www.openshorts.app'
    ],
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/videos': { target: backend, changeOrigin: true },
      '/thumbnails': { target: backend, changeOrigin: true },
      '/gallery': { target: backend, changeOrigin: true },
      '/video': { target: backend, changeOrigin: true },
      '/render': { target: renderer, changeOrigin: true },
    }
  },
  // `npm run start` (vite preview) needs the same proxy or /api/* 404s
  // and the app boots against nothing.
  preview: {
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/videos': { target: backend, changeOrigin: true },
      '/thumbnails': { target: backend, changeOrigin: true },
      '/gallery': { target: backend, changeOrigin: true },
      '/video': { target: backend, changeOrigin: true },
      '/render': { target: renderer, changeOrigin: true },
    }
  }
})
