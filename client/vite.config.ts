import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const apiOrigin = process.env.ARCVELLUM_API_ORIGIN ?? "http://127.0.0.1:8791";
const clientPort = Number.parseInt(process.env.ARCVELLUM_CLIENT_PORT ?? "5173", 10);

export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  base: "/ui/",
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: fileURLToPath(new URL("../src/literary_engineering_studio/frontend/dist", import.meta.url)),
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    host: "127.0.0.1",
    port: Number.isFinite(clientPort) ? clientPort : 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiOrigin,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
