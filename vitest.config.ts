import { defineConfig } from "vitest/config"

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["test/**/*.test.ts", ".config/opencode/plugins/**/*.test.ts"],
    exclude: ["node_modules", ".config/opencode/node_modules"],
  },
})
