import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API runs on 127.0.0.1:8000 (uvicorn api.main:app). Vite proxies /api so there is no CORS.
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5317, strictPort: true, proxy: { "/api": "http://127.0.0.1:8000" } },
});
