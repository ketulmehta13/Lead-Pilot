/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// In Docker the backend is reachable as http://backend:8000; locally it is localhost.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Lazy page chunks (charts, drag-and-drop) can take seconds to load on a busy machine.
    testTimeout: 20_000,
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
