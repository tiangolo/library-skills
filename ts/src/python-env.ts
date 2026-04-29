import { existsSync, readdirSync } from "node:fs";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";

export function findProjectRoot(cwd: string): string | null {
  for (const directory of ancestors(cwd)) {
    if (
      existsSync(join(directory, "pyproject.toml")) ||
      existsSync(join(directory, "uv.lock")) ||
      existsSync(join(directory, ".venv", "pyvenv.cfg"))
    ) {
      return directory;
    }
  }
  return null;
}

export function findVenv(cwd = process.cwd()): string | null {
  const projectRoot = findProjectRoot(cwd) ?? cwd;

  const uvProjectEnvironment = process.env["UV_PROJECT_ENVIRONMENT"];
  if (uvProjectEnvironment) {
    const path = isAbsolute(uvProjectEnvironment)
      ? uvProjectEnvironment
      : join(projectRoot, uvProjectEnvironment);
    if (isVenvDir(path)) {
      return path;
    }
  }

  for (const directory of ancestors(cwd)) {
    const dotVenv = join(directory, ".venv");
    if (isVenvDir(dotVenv)) {
      return dotVenv;
    }
  }

  const virtualEnv = process.env["VIRTUAL_ENV"];
  if (virtualEnv && isVenvDir(virtualEnv) && isRelativeTo(virtualEnv, projectRoot)) {
    return virtualEnv;
  }

  const condaPrefix = process.env["CONDA_PREFIX"];
  if (condaPrefix && existsSync(condaPrefix)) {
    return condaPrefix;
  }

  return null;
}

export function getSitePackagesDir(venvPath: string): string | null {
  const windowsSitePackages = join(venvPath, "Lib", "site-packages");
  if (existsSync(windowsSitePackages)) {
    return windowsSitePackages;
  }

  for (const libName of ["lib", "lib64"]) {
    const libDir = join(venvPath, libName);
    if (!existsSync(libDir)) {
      continue;
    }

    for (const child of readdirSync(libDir).sort().reverse()) {
      const sitePackages = join(libDir, child, "site-packages");
      if (child.startsWith("python") && existsSync(sitePackages)) {
        return sitePackages;
      }
    }
  }

  return null;
}

export const getSitePackages = getSitePackagesDir;

function isVenvDir(directory: string): boolean {
  return existsSync(join(directory, "pyvenv.cfg"));
}

function ancestors(start: string): string[] {
  const result: string[] = [];
  let directory = resolve(start);
  while (true) {
    result.push(directory);
    const parent = dirname(directory);
    if (parent === directory) {
      break;
    }
    directory = parent;
  }
  return result;
}

function isRelativeTo(path: string, parent: string): boolean {
  const normalizedPath = resolve(path);
  const normalizedParent = resolve(parent);
  return (
    normalizedPath === normalizedParent ||
    normalizedPath.startsWith(`${normalizedParent}${sep}`)
  );
}
