import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Helper to resolve SSL certificate if available
function getHttpsConfig() {
  const possibleCerts = [
    { cert: 'certs/cert.pem', key: 'certs/key.pem' },
    { cert: '../10.196.199.15.pem', key: '../10.196.199.15-key.pem' },
    { cert: '10.196.199.15.pem', key: '10.196.199.15-key.pem' },
  ]

  for (const pair of possibleCerts) {
    const certPath = path.resolve(__dirname, pair.cert)
    const keyPath = path.resolve(__dirname, pair.key)
    if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
      return {
        cert: fs.readFileSync(certPath),
        key: fs.readFileSync(keyPath),
      }
    }
  }
  return undefined
}

const httpsConfig = getHttpsConfig()

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-dom/client',
      'lucide-react',
      'xlsx',
      'katex',
      'jszip',
      'react-router-dom',
    ],
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    allowedHosts: true,
    https: httpsConfig,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:1409',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
    host: '0.0.0.0',
    allowedHosts: true,
    https: httpsConfig,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:1409',
        changeOrigin: true,
      },
    },
  },
})
