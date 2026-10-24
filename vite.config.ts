import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "./",
  plugins: [vue()],
  resolve: { alias: { "@": fileURLToPath(new URL("./apps/web/src", import.meta.url)) } },
  server: { host: "127.0.0.1", port: 5173, strictPort: true },
  build: { outDir: "apps/web/dist", emptyOutDir: true, sourcemap: false }
});
