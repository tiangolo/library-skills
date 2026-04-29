import {
  existsSync,
  lstatSync,
  mkdtempSync,
  mkdirSync,
  readlinkSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { createProgram } from "../src/cli.js";
import { getPythonTopLevelDeps } from "../src/deps.js";
import {
  InstallError,
  installSkill,
  listInstalledSkills,
  uninstallSkill,
} from "../src/installer.js";
import {
  findProjectRoot,
  findVenv,
  getSitePackagesDir,
} from "../src/python-env.js";
import {
  normalizePackageName,
  scanPythonDistributions,
  testing as scannerTesting,
  type Skill,
} from "../src/scanner.js";

let tempDirs: string[] = [];
let originalCwd: string;
let originalEnv: NodeJS.ProcessEnv;

beforeEach(() => {
  originalCwd = process.cwd();
  originalEnv = { ...process.env };
});

afterEach(() => {
  process.chdir(originalCwd);
  process.env = originalEnv;
  for (const directory of tempDirs.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
  vi.restoreAllMocks();
});

test("scans Python distribution RECORD entries for valid skills", () => {
  const sitePackages = tempDir();
  writeDistribution({
    sitePackages,
    distInfoName: "example_pkg-1.0.0.dist-info",
    packageName: "Example-Pkg",
    version: "1.0.0",
    records: ["example_pkg/.agents/skills/hello/SKILL.md,,"],
  });
  writeSkill(
    join(sitePackages, "example_pkg", ".agents", "skills", "hello"),
    "hello",
    "Greets a user.",
  );

  const result = scanPythonDistributions(sitePackages);

  expect(result.warnings).toEqual([]);
  expect(result.skills).toMatchObject([
    {
      name: "hello",
      description: "Greets a user.",
      packageName: "Example-Pkg",
      packageVersion: "1.0.0",
    },
  ]);
});

test("reports invalid distribution and skill metadata without returning invalid skills", () => {
  const sitePackages = tempDir();
  mkdirSync(join(sitePackages, "bad-1.0.0.dist-info"), { recursive: true });
  writeDistribution({
    sitePackages,
    distInfoName: "invalid_skill-1.0.0.dist-info",
    packageName: "invalid-skill",
    version: "1.0.0",
    records: ["invalid_skill/.agents/skills/Bad/SKILL.md,,"],
  });
  writeSkill(
    join(sitePackages, "invalid_skill", ".agents", "skills", "Bad"),
    "Bad",
    "Uppercase names are invalid.",
  );

  const result = scanPythonDistributions(sitePackages);

  expect(result.skills).toEqual([]);
  expect(result.warnings).toEqual(
    expect.arrayContaining([
      expect.stringContaining("Skipping invalid distribution metadata"),
      expect.stringContaining("invalid 'name' field"),
    ]),
  );
});

test("discovers editable skills from direct_url.json file URLs", () => {
  const sitePackages = tempDir();
  const sourceRoot = tempDir();
  writeSkill(
    join(sourceRoot, ".agents", "skills", "editable"),
    "editable",
    "Editable package skill.",
  );
  const distInfo = writeDistribution({
    sitePackages,
    distInfoName: "editable_pkg-1.0.0.dist-info",
    packageName: "editable-pkg",
    version: "1.0.0",
    records: [],
  });
  writeFileSync(
    join(distInfo, "direct_url.json"),
    JSON.stringify({
      dir_info: { editable: true },
      url: pathToFileURL(sourceRoot).href,
    }),
  );

  const result = scanPythonDistributions(sitePackages);

  expect(result.warnings).toEqual([]);
  expect(result.skills.map((skill) => skill.name)).toEqual(["editable"]);
});

test("scanner helpers parse CSV and normalize package names", () => {
  expect(scannerTesting.isSkillFileRecord("pkg/.agents/skills/demo/SKILL.md")).toBe(true);
  expect(scannerTesting.isSkillFileRecord("pkg/.agents/other/demo/SKILL.md")).toBe(false);
  expect(normalizePackageName("Example_Pkg.Name")).toBe("example-pkg-name");
});

test("scans quoted CSV paths in distribution RECORD entries", () => {
  const sitePackages = tempDir();
  writeDistribution({
    sitePackages,
    distInfoName: "quoted_pkg-1.0.0.dist-info",
    packageName: "quoted-pkg",
    version: "1.0.0",
    records: ['"quoted_pkg/.agents/skills/quoted/SKILL.md",sha256=abc,123'],
  });
  writeSkill(
    join(sitePackages, "quoted_pkg", ".agents", "skills", "quoted"),
    "quoted",
    "Quoted CSV path.",
  );

  const result = scanPythonDistributions(sitePackages);

  expect(result.skills.map((skill) => skill.name)).toEqual(["quoted"]);
});

test("parses project dependency names from pyproject.toml", () => {
  const project = tempDir();
  writeFileSync(
    join(project, "pyproject.toml"),
    [
      "[project]",
      'dependencies = ["Example_Pkg>=1", "requests[security]; python_version >= \\"3.11\\""]',
      "[project.optional-dependencies]",
      'dev = ["PyTest < 9"]',
      "",
    ].join("\n"),
  );

  expect(getPythonTopLevelDeps(project)).toEqual(
    new Set(["example-pkg", "requests", "pytest"]),
  );
});

test("resolves project virtualenvs and site-packages", () => {
  const project = tempDir();
  const nested = join(project, "src", "pkg");
  const venv = join(project, ".venv");
  const sitePackages = join(venv, "lib", "python3.12", "site-packages");
  mkdirSync(nested, { recursive: true });
  mkdirSync(sitePackages, { recursive: true });
  writeFileSync(join(project, "pyproject.toml"), "[project]\nname = 'demo'\n");
  writeFileSync(join(venv, "pyvenv.cfg"), "");

  expect(findProjectRoot(nested)).toBe(project);
  expect(findVenv(nested)).toBe(venv);
  expect(getSitePackagesDir(venv)).toBe(sitePackages);
});

test("honors UV_PROJECT_ENVIRONMENT before local .venv", () => {
  const project = tempDir();
  const uvEnv = join(project, ".custom-env");
  mkdirSync(uvEnv, { recursive: true });
  writeFileSync(join(project, "pyproject.toml"), "[project]\nname = 'demo'\n");
  writeFileSync(join(uvEnv, "pyvenv.cfg"), "");
  process.env["UV_PROJECT_ENVIRONMENT"] = ".custom-env";

  expect(findVenv(project)).toBe(uvEnv);
});

describe("installer", () => {
  test("installs relative symlinks, lists them, and removes only symlinks", () => {
    const root = tempDir();
    const source = writeSkill(join(root, "source", "agent"), "agent", "Agent skill.");
    const targetDir = join(root, ".agents", "skills");
    const skill = makeSkill({ name: "agent", skillDir: source });

    const dest = installSkill(skill, targetDir);

    expect(lstatSync(dest).isSymbolicLink()).toBe(true);
    expect(readlinkSync(dest)).not.toMatch(/^[/A-Za-z]:/);
    expect(listInstalledSkills(targetDir)).toMatchObject([
      { name: "agent", type: "symlink", hasSkillMd: true, target: source },
    ]);
    expect(uninstallSkill("agent", targetDir)).toBe(true);
    expect(existsSync(dest)).toBe(false);
  });

  test("refuses to overwrite hand-authored directories", () => {
    const root = tempDir();
    const source = writeSkill(join(root, "source", "agent"), "agent", "Agent skill.");
    const targetDir = join(root, ".agents", "skills");
    mkdirSync(join(targetDir, "agent"), { recursive: true });

    expect(() =>
      installSkill(makeSkill({ name: "agent", skillDir: source }), targetDir),
    ).toThrow(InstallError);
  });
});

test("CLI scan defaults to top-level project dependencies", async () => {
  const project = writeProjectWithTopLevelAndTransitiveSkills();
  process.chdir(project);
  vi.spyOn(console, "log").mockImplementation(() => undefined);
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  const table = vi.spyOn(console, "table").mockImplementation(() => undefined);

  await createProgram().parseAsync(["node", "library-skills", "scan"]);

  expect(table).toHaveBeenCalledWith([
    expect.objectContaining({ Skill: "top-skill", Package: "top-level-pkg" }),
  ]);
});

test("CLI installs all discovered skills with --yes --all", async () => {
  const project = writeProjectWithTopLevelAndTransitiveSkills();
  process.chdir(project);
  vi.spyOn(console, "log").mockImplementation(() => undefined);
  vi.spyOn(console, "error").mockImplementation(() => undefined);

  await createProgram().parseAsync(["node", "library-skills", "install", "--yes", "--all"]);

  expect(existsSync(join(project, ".agents", "skills", "top-skill"))).toBe(true);
  expect(existsSync(join(project, ".agents", "skills", "transitive-skill"))).toBe(true);
});

function tempDir(): string {
  const directory = mkdtempSync(join(tmpdir(), "library-skills-ts-"));
  tempDirs.push(directory);
  return directory;
}

function writeDistribution({
  sitePackages,
  distInfoName,
  packageName,
  version,
  records,
}: {
  sitePackages: string;
  distInfoName: string;
  packageName: string;
  version: string;
  records: string[];
}): string {
  const distInfo = join(sitePackages, distInfoName);
  mkdirSync(distInfo, { recursive: true });
  writeFileSync(join(distInfo, "METADATA"), `Name: ${packageName}\nVersion: ${version}\n`);
  writeFileSync(join(distInfo, "RECORD"), records.join("\n"));
  return distInfo;
}

function writeSkill(directory: string, name: string, description: string): string {
  mkdirSync(directory, { recursive: true });
  writeFileSync(
    join(directory, "SKILL.md"),
    `---\nname: ${name}\ndescription: ${description}\n---\n\nUse this skill.\n`,
  );
  return directory;
}

function writePackageSkill({
  sitePackages,
  packageDir,
  skillName,
  packageName,
}: {
  sitePackages: string;
  packageDir: string;
  skillName: string;
  packageName: string;
}): void {
  writeDistribution({
    sitePackages,
    distInfoName: `${packageDir}-1.0.0.dist-info`,
    packageName,
    version: "1.0.0",
    records: [`${packageDir}/.agents/skills/${skillName}/SKILL.md,,`],
  });
  writeSkill(
    join(sitePackages, packageDir, ".agents", "skills", skillName),
    skillName,
    `${skillName} description.`,
  );
}

function writeProjectWithTopLevelAndTransitiveSkills(): string {
  const project = tempDir();
  const sitePackages = join(project, ".venv", "lib", "python3.12", "site-packages");
  mkdirSync(sitePackages, { recursive: true });
  writeFileSync(join(project, ".venv", "pyvenv.cfg"), "");
  writeFileSync(
    join(project, "pyproject.toml"),
    "[project]\ndependencies = ['top-level-pkg']\n",
  );
  writePackageSkill({
    sitePackages,
    packageDir: "top_level_pkg",
    skillName: "top-skill",
    packageName: "top-level-pkg",
  });
  writePackageSkill({
    sitePackages,
    packageDir: "transitive_pkg",
    skillName: "transitive-skill",
    packageName: "transitive-pkg",
  });
  return project;
}

function makeSkill({ name, skillDir }: { name: string; skillDir: string }): Skill {
  return {
    name,
    description: "A useful skill.",
    path: join(skillDir, "SKILL.md"),
    packageName: "demo-package",
    packageVersion: "1.0.0",
    skillDir,
  };
}
