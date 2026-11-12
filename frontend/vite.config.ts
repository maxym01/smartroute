/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// Dev server przekazuje /api do backendu FastAPI — przeglądarka widzi jeden origin,
// więc CORS nie jest potrzebny w trybie deweloperskim.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendUrl = env.VITE_BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000';

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': { target: backendUrl, changeOrigin: true },
      },
    },
    preview: {
      port: 4173,
      proxy: {
        '/api': { target: backendUrl, changeOrigin: true },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  };
});
