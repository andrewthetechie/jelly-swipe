/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  // Vitest configuration lives here (not a separate vitest.config.js) so a
  // beginner has one config file to reason about, and the React plugin above
  // is reused automatically for transforming JSX/TSX in tests.
  test: {
    // jsdom gives tests a fake browser DOM (document, window, elements).
    environment: 'jsdom',
    // globals: true exposes describe/it/expect/vi without importing them in
    // every file, so tests read more naturally for someone new to Vitest.
    globals: true,
    // setupFiles runs before each test file; ours registers the jest-dom
    // matchers (toBeInTheDocument, etc.).
    setupFiles: ['test/setup.ts'],
  },
});
