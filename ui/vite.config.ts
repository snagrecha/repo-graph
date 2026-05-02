import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:7842',
      '/mcp': 'http://localhost:7842',
      '/ws': { target: 'ws://localhost:7842', ws: true, changeOrigin: true },
    },
  },
});
