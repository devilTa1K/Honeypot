import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// Dev proxy: UI on :5173, honeypot API on :8000 (or set HIAB_API)
const api = process.env.HIAB_API || 'http://127.0.0.1:8000'
export default defineConfig({ plugins: [react()],
  server: { proxy: { '/admin': api, '/ws': { target: api.replace('http', 'ws'), ws: true } } } })
