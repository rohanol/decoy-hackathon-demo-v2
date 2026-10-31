import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// AGENTS.md section 3: Vite is bound to 127.0.0.1:5173. Never 0.0.0.0 — the lab
// link must not serve the SOC UI to the attacker laptop.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    fs: {
      // The fixture lives in contracts/, which M3 owns. We import it read-only
      // rather than copying it into frontend/, so it can never drift from the
      // contract. Paths are relative to this project root; contracts/ is the
      // only folder outside frontend/ the dev server may read.
      allow: ['.', '../contracts'],
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
