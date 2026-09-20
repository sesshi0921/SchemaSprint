import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        id: '/',
        name: 'SchemaSprint',
        short_name: 'SchemaSprint',
        lang: 'en',
        description: 'Practice database design with one thoughtful problem every day.',
        theme_color: '#5654A2',
        background_color: '#f4f5f7',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        orientation: 'any',
        categories: ['education', 'productivity'],
        icons: [{ src: '/favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }],
      },
      workbox: { navigateFallback: '/', cleanupOutdatedCaches: true, globIgnores: ['**/elk.bundled-*.js'] },
    }),
  ],
  server: { port: 5173 },
})
