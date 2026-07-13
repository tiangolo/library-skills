import {
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  readlinkSync,
  rmSync,
  statSync,
  symlinkSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import type { Skill } from "./scanner.js";

export const UNIVERSAL_SKILLS_DIR = ".agents/skills";
export const CLAUDE_SKILLS_DIR = ".claude/skills";
export const KIRO_SKILLS_DIR = ".kiro/skills";
export const TOOL_SKILL_NAME = "library-skills";
export const TOOL_SKILL_MARKER = ".library-skills.json";
export const TOOL_SKILL_KIND = "tool-skill";

export interface FrameworkConfig {
  name: string;
  displayName: string;
  shortName: string;
  skillsDir: string;
  detectorDir: string;
  cliFlag: string;
}

export const FRAMEWORKS: Record<string, FrameworkConfig> = {
  claude: {
    name: "claude-compatible",
    displayName: "Claude Code (.claude/skills)",
    shortName: "Claude Code",
    skillsDir: ".claude/skills",
    detectorDir: ".claude",
    cliFlag: "--claude",
  },
  kiro: {
    name: "kiro-compatible",
    displayName: "Kiro (.kiro/skills)",
    shortName: "Kiro",
    skillsDir: ".kiro/skills",
    detectorDir: ".kiro",
    cliFlag: "--kiro",
  },
};

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

export interface ToolSkillStatus {
  target: InstallTarget;
  path: string;
  status:
    | "tool skill: missing"
    | "tool skill: up to date"
    | "tool skill: stale"
    | "tool skill: invalid marker"
    | "tool skill: blocked by hand-authored directory";
}

export class InstallError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InstallError";
  }
}

export class ToolSkillError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ToolSkillError";
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

export function getAllTargetDirs(projectRoot: string): InstallTarget[] {
  return getTargetDirs(projectRoot, { includeClaude: true });
}

export function getDefaultInstallTargetDirs(projectRoot: string): InstallTarget[] {
  const [universal, claude] = getAllTargetDirs(projectRoot);

  const selected: InstallTarget[] = [];
  if (existsSync(join(projectRoot, ".agents"))) {
    selected.push(universal);
  }
  if (existsSync(join(projectRoot, ".claude"))) {
    selected.push(claude);
  }

  return selected.length > 0 ? selected : [universal];
}

export function getExistingTargetDirs(
  projectRoot: string,
  options: { includeClaude?: boolean } = {},
): InstallTarget[] {
  if (options.includeClaude) {
    return getTargetDirs(projectRoot, { includeClaude: true });
  }
  return getAllTargetDirs(projectRoot).filter((target) => isDirectory(target.path));
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
    try {
      symlinkSync(getSymlinkTarget({ source, dest }), dest, "dir");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new InstallError(
        `Could not create symlink: ${message}. Use --copy if your system does not support symlinks.`,
      );
    }
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

export function inspectToolSkill(targetDir: string, template: string): ToolSkillStatus {
  const target = targetForPath(targetDir);
  const dest = join(targetDir, TOOL_SKILL_NAME);
  const marker = join(dest, TOOL_SKILL_MARKER);
  const skillMd = join(dest, "SKILL.md");

  if (!existsSync(dest) && !isSymlink(dest)) {
    return { target, path: dest, status: "tool skill: missing" };
  }
  if (isSymlink(dest) || !isDirectory(dest)) {
    return {
      target,
      path: dest,
      status: "tool skill: blocked by hand-authored directory",
    };
  }
  if (!isManagedToolSkillMarker(marker)) {
    return {
      target,
      path: dest,
      status: existsSync(marker)
        ? "tool skill: invalid marker"
        : "tool skill: blocked by hand-authored directory",
    };
  }
  if (!existsSync(skillMd)) {
    return { target, path: dest, status: "tool skill: stale" };
  }
  const status =
    readFileSync(skillMd, "utf-8") === template
      ? "tool skill: up to date"
      : "tool skill: stale";
  return { target, path: dest, status };
}

export function installToolSkill({
  targetDir,
  template,
  version,
}: {
  targetDir: string;
  template: string;
  version: string;
}): string {
  const status = inspectToolSkill(targetDir, template);
  if (
    status.status === "tool skill: blocked by hand-authored directory" ||
    status.status === "tool skill: invalid marker"
  ) {
    throw new ToolSkillError(`Cannot overwrite ${status.status}: ${status.path}`);
  }

  const dest = join(targetDir, TOOL_SKILL_NAME);
  if (existsSync(dest)) {
    rmSync(dest, { recursive: true, force: true });
  }
  mkdirSync(dest, { recursive: true });
  writeFileSync(join(dest, "SKILL.md"), template, "utf-8");
  writeFileSync(
    join(dest, TOOL_SKILL_MARKER),
    `${JSON.stringify(
      { kind: TOOL_SKILL_KIND, version },
      null,
      2,
    )}\n`,
    "utf-8",
  );
  return dest;
}

export function listInstalledSkills(targetDir: string): InstalledSkill[] {
  if (!isDirectory(targetDir)) {
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

function targetForPath(targetDir: string): InstallTarget {
  return targetDir.endsWith(CLAUDE_SKILLS_DIR)
    ? { name: "claude-compatible", path: targetDir }
    : { name: "universal", path: targetDir };
}

function isManagedToolSkillMarker(marker: string): boolean {
  try {
    const data = JSON.parse(readFileSync(marker, "utf-8")) as { kind?: unknown };
    return data.kind === TOOL_SKILL_KIND;
  } catch {
    return false;
  }
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
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

export const testing = {
	getSymlinkTarget,
	isDirectory,
	isSymlink,
	resolveSymlink,
};
