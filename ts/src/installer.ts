import {
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readlinkSync,
  rmSync,
  symlinkSync,
  unlinkSync,
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import type { Skill } from "./scanner.js";

export const UNIVERSAL_SKILLS_DIR = ".agents/skills";
export const CLAUDE_SKILLS_DIR = ".claude/skills";

export interface InstallTarget {
  name: string;
  path: string;
}

export interface InstalledSkill {
  name: string;
  type: "symlink" | "directory";
  path: string;
  target: string | null;
  hasSkillMd: boolean;
}

export class InstallError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InstallError";
  }
}

export function getTargetDirs(
  projectRoot: string,
  options: { includeClaude?: boolean } = {},
): InstallTarget[] {
  const targets: InstallTarget[] = [
    { name: "universal", path: join(projectRoot, UNIVERSAL_SKILLS_DIR) },
  ];
  if (options.includeClaude) {
    targets.push({
      name: "claude-compatible",
      path: join(projectRoot, CLAUDE_SKILLS_DIR),
    });
  }
  return targets;
}

export function installSkill(
  skill: Skill,
  targetDir: string,
  options: { copy?: boolean } = {},
): string {
  const dest = join(targetDir, skill.name);
  const source = resolve(skill.skillDir);

  if (existsSync(dest) || isSymlink(dest)) {
    if (isSymlink(dest)) {
      unlinkSync(dest);
    } else if (lstatSync(dest).isFile()) {
      throw new InstallError(`Cannot overwrite non-symlink file: ${dest}`);
    } else if (lstatSync(dest).isDirectory()) {
      throw new InstallError(`Cannot overwrite non-symlink directory: ${dest}`);
    }
  }

  mkdirSync(dirname(dest), { recursive: true });

  if (options.copy) {
    cpSync(source, dest, { recursive: true });
  } else {
    symlinkSync(getSymlinkTarget({ source, dest }), dest, "dir");
  }

  return dest;
}

export function uninstallSkill(skillName: string, targetDir: string): boolean {
  const dest = join(targetDir, skillName);
  if (isSymlink(dest)) {
    unlinkSync(dest);
    return true;
  }
  return false;
}

export function listInstalledSkills(targetDir: string): InstalledSkill[] {
  if (!existsSync(targetDir)) {
    return [];
  }

  return readdirSync(targetDir)
    .sort()
    .flatMap((name) => {
      const path = join(targetDir, name);
      if (!isSymlink(path) && !isDirectory(path)) {
        return [];
      }

      const type = isSymlink(path) ? "symlink" : "directory";
      return [
        {
          name,
          type,
          path,
          target: type === "symlink" ? resolveSymlink(path) : null,
          hasSkillMd: existsSync(join(path, "SKILL.md")),
        } satisfies InstalledSkill,
      ];
    });
}

function getSymlinkTarget({ source, dest }: { source: string; dest: string }): string {
  const relativeTarget = relative(dirname(resolve(dest)), source);
  return relativeTarget === "" ? source : relativeTarget;
}

function resolveSymlink(path: string): string | null {
  try {
    return resolve(dirname(path), readlinkSync(path));
  } catch {
    return null;
  }
}

function isSymlink(path: string): boolean {
  try {
    return lstatSync(path).isSymbolicLink();
  } catch {
    return false;
  }
}

function isDirectory(path: string): boolean {
  try {
    return lstatSync(path).isDirectory();
  } catch {
    return false;
  }
}

export const testing = {
  getSymlinkTarget,
};
