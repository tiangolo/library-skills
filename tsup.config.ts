import { defineConfig } from "tsup";

export default defineConfig([
  {
    entry: [
      "ts/src/index.ts",
      "ts/src/python-env.ts",
      "ts/src/scanner.ts",
      "ts/src/deps.ts",
      "ts/src/installer.ts",
    ],
    outDir: "ts/dist",
    format: ["esm", "cjs"],
    dts: true,
    clean: true,
  },
  {
    entry: ["ts/src/cli.ts"],
    outDir: "ts/dist",
    format: ["esm"],
    dts: true,
    clean: false,
  },
]);
