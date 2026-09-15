import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    // Ensure pdfjs-dist is pre-bundled correctly
    include: ['react-pdf', 'pdfjs-dist'],
  },
  build: {
    rollupOptions: {
      output: {
        // Keep the PDF worker as a separate chunk
        manualChunks: {
          'pdf-worker': ['pdfjs-dist'],
        },
      },
    },
  },
})
