import { defineConfig } from "vitest/config";

// Only the Electron-free modules are unit tested; everything under test/ runs in plain node.
export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
  },
});
