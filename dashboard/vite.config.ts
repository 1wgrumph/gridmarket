import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    fs: { allow: ['.', '../spec'] },
    // Local dev: serve the API from the backend on :8000, not index.html.
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/kit': 'http://127.0.0.1:8000',
      '/llms.txt': 'http://127.0.0.1:8000',
    },
  },
  test: { environment: 'jsdom' },
});
