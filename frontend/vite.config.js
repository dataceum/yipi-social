import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
//
// The backend's CORS_ALLOWED_ORIGINS (backend/.env) only allows
// http://localhost:3000, so the dev server runs on port 3000 and proxies
// /api straight through to FastAPI (default: http://localhost:8000). That
// keeps every request same-origin from the browser's point of view, so no
// CORS configuration changes are needed on either side.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
