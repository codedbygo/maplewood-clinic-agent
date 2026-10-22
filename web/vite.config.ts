import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vite build and dev server. Test settings live in vitest.config.ts.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  // In dev, the console API (make ui-dev) answers /api; in production it serves this build itself.
  server: { port: 5173, strictPort: true, proxy: { "/api": "http://127.0.0.1:8000" } },
  preview: { port: 4173, strictPort: true },
  build: {
    sourcemap: true,
    // A chunk over this size is a review question, not a warning to silence.
    chunkSizeWarningLimit: 500,
  },
});
