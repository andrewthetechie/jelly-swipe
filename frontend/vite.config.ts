/// <reference types="vitest/config" />
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { VitePWA } from "vite-plugin-pwa"

const apiProxy = {
  target: "http://localhost:5005",
  changeOrigin: true,
}

const proxy = Object.fromEntries(
  ["/auth", "/room", "/matches", "/genres", "/cast", "/me", "/jellyfin", "/healthz", "/readyz", "/proxy"]
    .map((path) => [path, apiProxy]),
)

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
          { src: "icon-192.png", type: "image/png", sizes: "192x192" },
          { src: "icon-mask.png", type: "image/png", sizes: "512x512", purpose: "maskable" },
          { src: "icon-512.png", type: "image/png", sizes: "512x512" },
        ],
      },
    }),
  ],
  server: { proxy },
  preview: { proxy },
  root: ".",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["test/setup.ts"],
  },
})
