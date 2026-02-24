import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/chat/sessions': 'http://localhost:8000',
      '/chat/ws': {
        target: 'http://localhost:8000',
        ws: true,
      },
      '/eval': 'http://localhost:8000',
    },
  },
})
