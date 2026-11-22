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
      '/departmental': 'http://localhost:8010',
      '/forensics': 'http://localhost:8010',
      '/ocr': 'http://localhost:8010',
      '/compliance-reports': 'http://localhost:8010',
      '/management-reports': 'http://localhost:8010',
      '/chatbot': 'http://localhost:8010',
      '/health': 'http://localhost:8010',
      // NEXA advanced intelligence modules (added — were missing, causing
      // the endless "loading" on Fraud Network & Zimbabwe Intelligence pages)
      '/fraud-network': 'http://localhost:8010',
      '/zim': 'http://localhost:8010',
      '/timeline': 'http://localhost:8010',
      '/evidence': 'http://localhost:8010',
      '/historical': 'http://localhost:8010',
      '/predictive': 'http://localhost:8010',
      '/model-performance': 'http://localhost:8010',
    }
  }
});
