import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Read version from package.json
import { readFileSync } from "fs";
const packageJson = JSON.parse(
  readFileSync(path.resolve(__dirname, "package.json"), "utf-8"),
);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(packageJson.version),
  },
  build: {
    outDir: path.resolve(__dirname, "../src/mcpx/web/static"),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/mcp": "http://127.0.0.1:8000",
    },
  },
});
