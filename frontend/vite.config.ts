import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// При разработке фронт живёт на :5173 и проксирует /api на бэкенд :8080.
// В проде фронт собирается в dist/ и раздаётся самим FastAPI на :8080.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
  build: {
    outDir: "dist",
  },
});
