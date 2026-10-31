/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Local development only. The frontend never talks to a database or a provider
// directly: it only calls the FastAPI server defined by VITE_API_BASE.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
    passWithNoTests: false,
  },
})
