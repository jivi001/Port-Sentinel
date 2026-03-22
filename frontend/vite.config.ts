import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // recharts alone is ~525 kB minified; kept in its own chunk so the app shell stays small.
    chunkSizeWarningLimit: 560,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('recharts')) return 'recharts';
          if (id.includes('socket.io-client')) return 'socket-io';
          if (id.includes('@msgpack')) return 'msgpack';
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8600',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:8600',
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
