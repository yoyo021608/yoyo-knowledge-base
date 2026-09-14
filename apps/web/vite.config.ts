import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const config = {
  plugins: [react()],
  envDir: "../../",
  server: {
    port: 5173,
  },
  test: {
    environment: "node",
    include: ["*.test.ts"],
  },
};

export default defineConfig(config);
