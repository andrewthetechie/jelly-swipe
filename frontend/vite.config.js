/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from "vite-plugin-pwa";

const apiProxy = {
  target: "http://localhost:5005",
  changeOrigin: true,
};

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Jelly-Swipe",
        short_name: "Jelly-Swipe",
        description: "Tinder-style swiping for Jellyfin",
        theme_color: "#111111",
        background_color: "#111111",
        display: "standalone",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      "/auth": apiProxy,
      "/room": apiProxy,
      "/matches": apiProxy,
      "/genres": apiProxy,
      "/cast": apiProxy,
      "/me": apiProxy,
      "/jellyfin": apiProxy,
      "/healthz": apiProxy,
      "/readyz": apiProxy,
      "/proxy": apiProxy,
    },
  },
  preview: {
    proxy: {
      "/auth": apiProxy,
      "/room": apiProxy,
      "/matches": apiProxy,
      "/genres": apiProxy,
      "/cast": apiProxy,
      "/me": apiProxy,
      "/jellyfin": apiProxy,
      "/healthz": apiProxy,
      "/readyz": apiProxy,
      "/proxy": apiProxy,
    },
  },
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['test/setup.ts'],
  },
});
