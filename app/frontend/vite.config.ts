import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
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
