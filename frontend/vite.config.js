import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Windows + Docker bind mounts often miss native FS events; poll so nav/RBAC
    // source edits (e.g. navByRole.js) actually reach the running Vite process.
    watch: {
      usePolling: true,
      interval: 1000,
    },
  },
});
