import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["ts/tests/**/*.test.ts"],
    coverage: {
      exclude: ["ts/src/index.ts"],
      include: ["ts/src/**/*.ts"],
      reporter: ["text"],
      thresholds: {
        statements: 100,
        functions: 100,
        lines: 100,
      },
    },
  },
});
