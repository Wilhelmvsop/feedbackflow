/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  // The embeddable widget lives in /public and ships alongside the dashboard build.
  publicDir: '../public',
  server: { proxy: { '/api': backend, '/docs': backend, '/openapi.json': backend } },
  build: { outDir: '../backend/static', emptyOutDir: true },
  test: { globals: true, environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], restoreMocks: true },
})
