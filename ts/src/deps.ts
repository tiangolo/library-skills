import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parse, type TomlTable } from "smol-toml";
import { normalizePackageName } from "./scanner.js";

export function getPythonTopLevelDeps(projectRoot: string): Set<string> | null {
  const pyproject = join(projectRoot, "pyproject.toml");
  if (!existsSync(pyproject)) {
    return null;
  }

  let data: TomlTable;
  try {
    data = parse(readFileSync(pyproject, "utf8"));
  } catch {
    return null;
  }

  const deps = new Set<string>();

  const project = data["project"];
  if (!isRecord(project)) {
    return deps;
  }

  const dependencies = project["dependencies"];
  if (Array.isArray(dependencies)) {
    extractDepsFromSpecs(dependencies, deps);
  }

  const optionalDependencies = project["optional-dependencies"];
  if (isRecord(optionalDependencies)) {
    for (const groupDependencies of Object.values(optionalDependencies)) {
      if (Array.isArray(groupDependencies)) {
        extractDepsFromSpecs(groupDependencies, deps);
      }
    }
  }

  return deps;
}

function extractDepsFromSpecs(depSpecs: unknown[], deps: Set<string>): void {
  for (const depSpec of depSpecs) {
    if (typeof depSpec !== "string") {
      continue;
    }
    const packageName = depSpec.split(/[>=<![\];,\s]/)[0]?.trim();
    if (packageName && !packageName.startsWith("#")) {
      deps.add(normalizePackageName(packageName));
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const testing = {
	extractDepsFromSpecs,
	isRecord,
};
