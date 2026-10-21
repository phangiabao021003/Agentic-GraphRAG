/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Docker Desktop on Windows does not forward file-change events into the
    // container, so without polling Vite keeps serving stale modules.
    watch: process.env.VITE_USE_POLLING === "true" ? { usePolling: true, interval: 300 } : undefined,
  },
  test: {
    environment: "happy-dom",
  },
});
