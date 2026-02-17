/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunks - separate heavy dependencies
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-katex': ['katex', 'react-katex'],
          'vendor-icons': ['lucide-react'],
        },
      },
    },
    // Increase chunk size warning limit since we're splitting intentionally
    chunkSizeWarningLimit: 300,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/testSetup.ts"],
    globals: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    exclude: ["e2e/**"]
  }
});
