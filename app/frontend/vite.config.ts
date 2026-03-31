import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    preact(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      injectRegister: false, // we register manually in main.tsx
      manifest: false, // we use our own manifest.json in public/
      devOptions: {
        enabled: true,
        type: 'module',
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,png,svg,ico,woff,woff2}'],
      },
    }),
  ],
  root: '.',
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8765',
      '/status': 'http://localhost:8765',
      '/start': 'http://localhost:8765',
      '/start-worktree': 'http://localhost:8765',
      '/kill': 'http://localhost:8765',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
