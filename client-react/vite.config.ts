import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  server: {
    port: 8849,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8896",
        changeOrigin: true,
      },
      "/media": {
        target: "http://127.0.0.1:8896",
        changeOrigin: true,
      },
      "/api-docs": {
        target: "http://127.0.0.1:8896",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8896",
        ws: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        // 全局注入 SCSS 变量
        additionalData: "",
      },
    },
  },
});
