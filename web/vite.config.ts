import { defineConfig } from "vite";

export default defineConfig({
  base: "./", // rutas relativas: funciona igual en GitHub Pages que en local
  build: { target: "es2022" },
  optimizeDeps: { exclude: ["onnxruntime-web"] },
});
