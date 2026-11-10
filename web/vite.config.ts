/// <reference types="vitest/config" />
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Production: FastAPI serves dist/ and everything under /api.
// Dev: Vite proxies /api to the app on :8080. With VITE_MOCK=1 the SPA answers
// /api itself from src/mock (dev only — never part of a production build).
export default defineConfig({
  base: "/",
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
