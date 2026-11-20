import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: '0.0.0.0',
    proxy: {
      '/api': 'http://localhost:8010',
      '/auth': 'http://localhost:8010',
      '/claims': 'http://localhost:8010',
      '/fraud': 'http://localhost:8010',
      '/investigations': 'http://localhost:8010',
      '/dashboard': 'http://localhost:8010',
      '/audit-logs': 'http://localhost:8010',
      '/customers': 'http://localhost:8010',
      '/policies': 'http://localhost:8010',
      '/notifications': 'http://localhost:8010',
      '/users': 'http://localhost:8010',
    }
  }
});
