import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";

export function findProjectRoot(cwd: string): string | null {
  for (const directory of ancestors(cwd)) {
    if (
        isFile(join(directory, "pyproject.toml")) ||
        isFile(join(directory, "uv.lock")) ||
        venvFromDotVenv(directory) !== null ||
        isFile(join(directory, "package.json")) ||
        isDirectory(join(directory, "node_modules"))
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
    const venv = venvFromDotVenv(directory);
    if (venv !== null) {
      return venv;
    }
  }

  const virtualEnv = process.env["VIRTUAL_ENV"];
  if (virtualEnv && isVenvDir(virtualEnv) && isRelativeTo(virtualEnv, projectRoot)) {
    return virtualEnv;
  }

  const condaPrefix = process.env["CONDA_PREFIX"];
  if (condaPrefix && isDirectory(condaPrefix)) {
    return condaPrefix;
  }

  return null;
}

export function getSitePackagesDir(venvPath: string): string | null {
  const windowsSitePackages = join(venvPath, "Lib", "site-packages");
  if (isDirectory(windowsSitePackages)) {
    return windowsSitePackages;
  }

  for (const libName of ["lib", "lib64"]) {
    const libDir = join(venvPath, libName);
    if (!isDirectory(libDir)) {
      continue;
    }

    for (const child of readdirSync(libDir).sort().reverse()) {
      const sitePackages = join(libDir, child, "site-packages");
      if (child.startsWith("python") && isDirectory(sitePackages)) {
        return sitePackages;
      }
    }
  }

  return null;
}

export const getSitePackages = getSitePackagesDir;

export function findNodeModules(cwd = process.cwd()): string | null {
  for (const directory of ancestors(cwd)) {
    const nodeModules = join(directory, "node_modules");
    if (isDirectory(nodeModules)) {
      return nodeModules;
    }
  }
  return null;
}

function isVenvDir(directory: string): boolean {
  return isFile(join(directory, "pyvenv.cfg"));
}

function venvFromDotVenv(projectRoot: string): string | null {
  const dotVenv = join(projectRoot, ".venv");
  if (isDirectory(dotVenv)) {
    return isVenvDir(dotVenv) ? dotVenv : null;
  }
  if (isFile(dotVenv)) {
    return readVenvRedirectFile(dotVenv);
  }
  return null;
}

function readVenvRedirectFile(path: string): string | null {
  let content: string;
  try {
    content = readFileSync(path, "utf8");
  } catch {
    /* v8 ignore next -- covers a race where .venv disappears between stat and read. */
    return null;
  }
  const redirect = content.split(/\r?\n/, 1)[0];
  if (!redirect) {
    return null;
  }
  const venv = isAbsolute(redirect) ? redirect : join(dirname(path), redirect);
  return isVenvDir(venv) ? venv : null;
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

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}
