/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// In development the app runs on :5173 and forwards API/admin calls to Django on
// :8000, so the browser sees ONE origin and the session cookie just works.
const django = "http://127.0.0.1:8000";
const GROUND = "#141413"; // dark is the default theme (STYLE_GUIDE.md)

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "favicon.ico", "apple-touch-icon-180x180.png"],
      manifest: {
        name: "311",
        short_name: "311",
        description: "An inbox for side-project ideas",
        display: "standalone",
        start_url: "/",
        background_color: GROUND,
        theme_color: GROUND,
        icons: [
          { src: "pwa-64x64.png", sizes: "64x64", type: "image/png" },
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
          {
            src: "maskable-icon-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // The app shell works offline; data always comes from the network.
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//, /^\/mcp/, /^\/static\//],
      },
    }),
  ],
  server: {
    // changeOrigin: false keeps the browser's Host header, so Django's CSRF origin
    // check sees the same site the page came from.
    proxy: {
      "/api": { target: django, changeOrigin: false },
      "/admin": { target: django, changeOrigin: false },
      "/static": { target: django, changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
