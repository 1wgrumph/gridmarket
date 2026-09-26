import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom' },
  // Local dev: serve the API from the backend on :8000, not index.html.
  server: {
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/kit': 'http://127.0.0.1:8000',
      '/llms.txt': 'http://127.0.0.1:8000',
    },
  },
});
