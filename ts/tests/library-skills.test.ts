import {
  existsSync,
  lstatSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readlinkSync,
  rmSync,
  symlinkSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import checkbox from "@inquirer/checkbox";
import { pathToFileURL } from "node:url";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { createProgram, main, testing as cliTesting } from "../src/cli.js";
import {
  getNodeTopLevelDeps,
  getPythonTopLevelDeps,
  getTopLevelDeps,
  testing as depsTesting,
} from "../src/deps.js";
import {
  getTargetDirs,
  InstallError,
  installSkill,
  listInstalledSkills,
  testing as installerTesting,
  uninstallSkill,
} from "../src/installer.js";
import {
  findProjectRoot,
  findNodeModules,
  findVenv,
  getSitePackagesDir,
} from "../src/python-env.js";
import {
  normalizePackageName,
  scanNodePackages,
  scanPythonDistributions,
  testing as scannerTesting,
  type Skill,
} from "../src/scanner.js";

vi.mock("@inquirer/checkbox", () => ({
  default: vi.fn(),
}));

let tempDirs: string[] = [];
let originalCwd: string;
let originalEnv: NodeJS.ProcessEnv;

beforeEach(() => {
  originalCwd = process.cwd();
  originalEnv = { ...process.env };
  vi.mocked(checkbox).mockReset();
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

test("scans Node packages for valid skills", () => {
  const nodeModules = tempDir();
  writeNodePackageSkill({
    nodeModules,
    packageName: "@scope/example-pkg",
    skillName: "node-skill",
    version: "2.0.0",
  });

  const result = scanNodePackages(nodeModules);

  expect(result.warnings).toEqual([]);
  expect(result.skills).toMatchObject([
    {
      name: "node-skill",
      description: "node-skill description.",
      packageName: "@scope/example-pkg",
      packageVersion: "2.0.0",
    },
  ]);
});

test("reports invalid Node package and skill metadata", () => {
  const nodeModules = tempDir();
  writeFileSync(join(nodeModules, "README.md"), "not a package");
  mkdirSync(join(nodeModules, "bad-pkg", ".agents", "skills", "bad-skill"), {
    recursive: true,
  });
  writeFileSync(
    join(nodeModules, "bad-pkg", ".agents", "skills", "bad-skill", "SKILL.md"),
    "---\nname: bad-skill\ndescription: Bad skill.\n---\n",
  );
  writeNodePackageSkill({
    nodeModules,
    packageName: "invalid-skill",
    skillName: "actual-name",
  });
  writeFileSync(
    join(
      nodeModules,
      "invalid-skill",
      ".agents",
      "skills",
      "actual-name",
      "SKILL.md",
    ),
    "---\nname: different-name\ndescription: Invalid skill.\n---\n",
  );
  mkdirSync(join(nodeModules, "array-pkg"), { recursive: true });
  writeFileSync(join(nodeModules, "array-pkg", "package.json"), "[]");
  mkdirSync(join(nodeModules, "nameless-pkg"), { recursive: true });
  writeFileSync(join(nodeModules, "nameless-pkg", "package.json"), "{}");
  mkdirSync(join(nodeModules, "empty-pkg"), { recursive: true });
  writeFileSync(
    join(nodeModules, "empty-pkg", "package.json"),
    JSON.stringify({ name: "empty-pkg" }),
  );
  symlinkSync(join(nodeModules, "invalid-skill"), join(nodeModules, "linked-skill"), "dir");

  const missing = join(tempDir(), "missing");
  expect(scanNodePackages(missing)).toMatchObject({
    skills: [],
    warnings: [`node_modules directory not found: ${missing}`],
  });

  const result = scanNodePackages(nodeModules);
  expect(result.skills).toEqual([]);
  expect(result.warnings).toEqual(
    expect.arrayContaining([
      expect.stringContaining("Skipping invalid package metadata"),
      expect.stringContaining("must match parent directory"),
    ]),
  );
  expect(scannerTesting.readNodePackageInfo(join(nodeModules, "array-pkg"))).toBeNull();
  expect(scannerTesting.readNodePackageInfo(join(nodeModules, "nameless-pkg"))).toBeNull();
  expect(scannerTesting.iterNodePackageRoots(nodeModules)).toContain(
    join(nodeModules, "invalid-skill"),
  );
  expect(scannerTesting.iterNodePackageRoots(nodeModules)).not.toContain(
    join(nodeModules, "README.md"),
  );
  expect(scannerTesting.findNodeSkillMarkdownFiles(join(nodeModules, "missing"))).toEqual(
    [],
  );
  expect(scannerTesting.findNodeSkillMarkdownFiles(join(nodeModules, "empty-pkg"))).toEqual(
    [],
  );
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

test("scanner covers distribution metadata, duplicate records, and missing paths", () => {
  const missing = join(tempDir(), "missing-site-packages");
  expect(scanPythonDistributions(missing)).toMatchObject({
    skills: [],
    warnings: [`Site-packages directory not found: ${missing}`],
  });

  const sitePackages = tempDir();
  writeFileSync(join(sitePackages, "not_a_dir-1.0.0.dist-info"), "");
  const noName = join(sitePackages, "no_name-1.0.0.dist-info");
  mkdirSync(noName, { recursive: true });
  writeFileSync(join(noName, "METADATA"), "Version: 1.0.0\n");
  writeFileSync(join(noName, "RECORD"), "");

  const noRecord = join(sitePackages, "no_record-1.0.0.dist-info");
  mkdirSync(noRecord, { recursive: true });
  writeFileSync(join(noRecord, "METADATA"), "Name: no-record\n");

  const folded = join(sitePackages, "folded-1.0.0.dist-info");
  mkdirSync(folded, { recursive: true });
  writeFileSync(
    join(folded, "METADATA"),
    "Ignored header line\nName: folded-pkg\nVersion: 1\n 2\n\nBody text\n",
  );
  writeFileSync(
    join(folded, "RECORD"),
    [
      "folded_pkg/not-a-skill.txt,,",
      "folded_pkg/.agents/skills/folded/SKILL.md,,",
      "folded_pkg/.agents/skills/folded/SKILL.md,,",
    ].join("\n"),
  );
  writeSkill(
    join(sitePackages, "folded_pkg", ".agents", "skills", "folded"),
    "folded",
    "Folded version skill.",
  );

  const result = scanPythonDistributions(sitePackages);

  expect(result.skills).toMatchObject([{ name: "folded", packageVersion: "1 2" }]);
  expect(result.warnings).toEqual([
    expect.stringContaining("Skipping invalid distribution metadata"),
  ]);
});

test("scanner reports invalid skill frontmatter and metadata variants", () => {
  const sitePackages = tempDir();
  writeDistribution({
    sitePackages,
    distInfoName: "invalids-1.0.0.dist-info",
    packageName: "invalids",
    version: "1.0.0",
    records: [
      "pkg/.agents/skills/broken-read/SKILL.md,,",
      "pkg/.agents/skills/missing-yaml/SKILL.md,,",
      "pkg/.agents/skills/unterminated/SKILL.md,,",
      "pkg/.agents/skills/missing-name/SKILL.md,,",
      "pkg/.agents/skills/wrong-dir/SKILL.md,,",
      "pkg/.agents/skills/missing-description/SKILL.md,,",
      "pkg/.agents/skills/too-long/SKILL.md,,",
      "pkg/.agents/skills/quoted/SKILL.md,,",
    ],
  });

  const brokenRead = join(sitePackages, "pkg", ".agents", "skills", "broken-read");
  mkdirSync(brokenRead, { recursive: true });
  symlinkSync(join(sitePackages, "missing.md"), join(brokenRead, "SKILL.md"));
  writeRawSkill(join(sitePackages, "pkg", ".agents", "skills", "missing-yaml"), "No metadata");
  writeRawSkill(
    join(sitePackages, "pkg", ".agents", "skills", "unterminated"),
    "---\nname: unterminated\n",
  );
  writeRawSkill(
    join(sitePackages, "pkg", ".agents", "skills", "missing-name"),
    "---\ndescription: Missing name.\n---\n",
  );
  writeSkill(
    join(sitePackages, "pkg", ".agents", "skills", "wrong-dir"),
    "different",
    "Wrong directory.",
  );
  writeRawSkill(
    join(sitePackages, "pkg", ".agents", "skills", "missing-description"),
    "---\nname: missing-description\n---\n",
  );
  writeSkill(
    join(sitePackages, "pkg", ".agents", "skills", "too-long"),
    "too-long",
    "x".repeat(1025),
  );
  writeRawSkill(
    join(sitePackages, "pkg", ".agents", "skills", "quoted"),
    "---\n# comment\nnot metadata\nother: ignored\nname: 'quoted'\ndescription: \"Quoted metadata.\"\n---\n",
  );

  const result = scanPythonDistributions(sitePackages);

  expect(result.skills.map((skill) => skill.name)).toEqual(["quoted"]);
  expect(result.warnings.join("\n")).toEqual(expect.stringContaining("could not read SKILL.md"));
  expect(result.warnings.join("\n")).toEqual(expect.stringContaining("missing YAML frontmatter"));
  expect(result.warnings.join("\n")).toEqual(expect.stringContaining("unterminated YAML frontmatter"));
  expect(result.warnings.join("\n")).toEqual(expect.stringContaining("missing required 'name' field"));
  expect(result.warnings.join("\n")).toEqual(expect.stringContaining("must match parent directory"));
  expect(result.warnings.join("\n")).toEqual(
    expect.stringContaining("missing required 'description' field"),
  );
  expect(result.warnings.join("\n")).toEqual(expect.stringContaining("at most 1024 characters"));
});

test("scanner handles editable direct_url edge cases", () => {
  const distInfo = tempDir();
  expect(scannerTesting.readEditableSourceRoot(distInfo)).toBeNull();

  for (const data of [
    "not json",
    "[]",
    JSON.stringify({ dir_info: { editable: false }, url: "file:///tmp" }),
    JSON.stringify({ dir_info: { editable: true } }),
    JSON.stringify({ dir_info: { editable: true }, url: "not a url" }),
    JSON.stringify({ dir_info: { editable: true }, url: pathToFileURL(join(distInfo, "missing")).href }),
  ]) {
    writeFileSync(join(distInfo, "direct_url.json"), data);
    expect(scannerTesting.readEditableSourceRoot(distInfo)).toBeNull();
  }

  const sitePackages = tempDir();
  const sourceRoot = tempDir();
  const outside = tempDir();
  writeSkill(join(sourceRoot, ".agents", "skills", "editable"), "editable", "Editable skill.");
  const duplicate = join(sourceRoot, ".agents", "skills", "duplicate");
  mkdirSync(duplicate, { recursive: true });
  symlinkSync(join(sourceRoot, ".agents", "skills", "editable", "SKILL.md"), join(duplicate, "SKILL.md"));
  symlinkSync(join(sourceRoot, ".agents", "skills", "editable", "SKILL.md"), join(duplicate, "OTHER.md"));
  writeSkill(join(sourceRoot, ".agents", "skills", "invalid-editable"), "wrong-name", "Invalid.");
  writeFileSync(join(sourceRoot, ".agents", "skills", "invalid-editable", "OTHER.md"), "");
  const leak = join(sourceRoot, ".agents", "skills", "leak");
  mkdirSync(leak, { recursive: true });
  const outsideSkill = writeSkill(join(outside, ".agents", "skills", "leak"), "leak", "Leak.");
  symlinkSync(join(outsideSkill, "SKILL.md"), join(leak, "SKILL.md"));
  const editableDist = writeDistribution({
    sitePackages,
    distInfoName: "editable-1.0.0.dist-info",
    packageName: "editable",
    version: "1.0.0",
    records: [],
  });
  writeFileSync(
    join(editableDist, "direct_url.json"),
    JSON.stringify({ dir_info: { editable: true }, url: pathToFileURL(sourceRoot).href }),
  );

  const result = scanPythonDistributions(sitePackages);
  expect(result.skills.map((skill) => skill.name)).toEqual(["editable"]);
  expect(result.warnings).toEqual([expect.stringContaining("must match parent directory")]);
  expect(scannerTesting.findSkillMarkdownFiles(join(sourceRoot, "missing"))).toEqual([]);
  expect(scannerTesting.isSkillMarkdownPath(sourceRoot, sourceRoot)).toBe(false);
  expect(scannerTesting.realpathOrResolve(join(sourceRoot, "missing"))).toBe(
    join(sourceRoot, "missing"),
  );
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

test("parses project dependency names from package.json", () => {
  const project = tempDir();
  writeFileSync(
    join(project, "package.json"),
    JSON.stringify({
      dependencies: { "@Scope/Example_Pkg": "^1.0.0" },
      devDependencies: { Vitest: "^4.0.0" },
      optionalDependencies: { "Optional.Pkg": "^1.0.0" },
      peerDependencies: { Peer_Pkg: "^1.0.0" },
    }),
  );

  expect(getNodeTopLevelDeps(project)).toEqual(
    new Set(["@scope/example-pkg", "vitest", "optional-pkg", "peer-pkg"]),
  );
});

test("combines Python and Node project dependency names", () => {
  const project = tempDir();
  writeFileSync(join(project, "pyproject.toml"), "[project]\ndependencies = ['Python_Pkg']\n");
  writeFileSync(
    join(project, "package.json"),
    JSON.stringify({ dependencies: { node_pkg: "^1.0.0" } }),
  );

  expect(getTopLevelDeps(project)).toEqual(new Set(["python-pkg", "node-pkg"]));
});

test("handles missing, invalid, and partial pyproject dependency metadata", () => {
  expect(getPythonTopLevelDeps(tempDir())).toBeNull();

  const invalid = tempDir();
  writeFileSync(join(invalid, "pyproject.toml"), "[project");
  expect(getPythonTopLevelDeps(invalid)).toBeNull();

  const noProject = tempDir();
  writeFileSync(join(noProject, "pyproject.toml"), "[tool.demo]\nname = 'demo'\n");
  expect(getPythonTopLevelDeps(noProject)).toEqual(new Set());

  const invalidProject = tempDir();
  writeFileSync(join(invalidProject, "pyproject.toml"), "project = 'demo'\n");
  expect(getPythonTopLevelDeps(invalidProject)).toEqual(new Set());

  const mixed = new Set<string>();
  depsTesting.extractDepsFromSpecs([1, "# ignored", "AnyIO>=4"], mixed);
  expect(mixed).toEqual(new Set(["anyio"]));
  expect(depsTesting.isRecord(null)).toBe(false);

  const optionalScalar = tempDir();
  writeFileSync(
    join(optionalScalar, "pyproject.toml"),
    "[project]\nname = 'demo'\n[project.optional-dependencies]\ndev = 'pytest'\n",
  );
  expect(getPythonTopLevelDeps(optionalScalar)).toEqual(new Set());

  expect(getNodeTopLevelDeps(tempDir())).toBeNull();
  const invalidPackage = tempDir();
  writeFileSync(join(invalidPackage, "package.json"), "{");
  expect(getNodeTopLevelDeps(invalidPackage)).toBeNull();

  const packageArray = tempDir();
  writeFileSync(join(packageArray, "package.json"), "[]");
  expect(getNodeTopLevelDeps(packageArray)).toEqual(new Set());
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

  const nodeProject = tempDir();
  const nodeNested = join(nodeProject, "src");
  mkdirSync(nodeNested, { recursive: true });
  writeFileSync(join(nodeProject, "package.json"), "{}");
  expect(findProjectRoot(nodeNested)).toBe(nodeProject);
  mkdirSync(join(nodeProject, "node_modules"), { recursive: true });
  expect(findNodeModules(nodeNested)).toBe(join(nodeProject, "node_modules"));
  expect(findNodeModules(tempDir())).toBeNull();

  const fileMarkerProject = tempDir();
  const fileMarkerNested = join(fileMarkerProject, "src");
  mkdirSync(fileMarkerNested, { recursive: true });
  writeFileSync(join(fileMarkerProject, "node_modules"), "not a directory");
  expect(findProjectRoot(fileMarkerNested)).toBeNull();
  expect(findNodeModules(fileMarkerNested)).toBeNull();
});

test("handles alternate and missing Python environment discovery paths", () => {
  const project = tempDir();
  const nested = join(project, "pkg");
  mkdirSync(nested, { recursive: true });
  writeFileSync(join(project, "uv.lock"), "");

  expect(findProjectRoot(join(project, "missing"))).toBe(project);
  expect(findProjectRoot(tempDir())).toBeNull();

  process.env["UV_PROJECT_ENVIRONMENT"] = "/missing-env";
  expect(findVenv(nested)).toBeNull();

  const outside = tempDir();
  writeFileSync(join(outside, "pyvenv.cfg"), "");
  process.env = { ...originalEnv, VIRTUAL_ENV: outside };
  expect(findVenv(nested)).toBeNull();

  const venv = join(project, "env");
  const windowsSitePackages = join(venv, "Lib", "site-packages");
  mkdirSync(windowsSitePackages, { recursive: true });
  writeFileSync(join(venv, "pyvenv.cfg"), "");
  process.env = { ...originalEnv, VIRTUAL_ENV: venv };
  expect(findVenv(nested)).toBe(venv);
  expect(getSitePackagesDir(venv)).toBe(windowsSitePackages);

  const conda = tempDir();
  process.env = { ...originalEnv, CONDA_PREFIX: conda };
  expect(findVenv(project)).toBe(conda);

  const condaFile = join(tempDir(), "conda-file");
  writeFileSync(condaFile, "not a directory");
  process.env = { ...originalEnv, CONDA_PREFIX: condaFile };
  expect(findVenv(project)).toBeNull();

  const noSitePackages = join(project, "no-site-packages");
  mkdirSync(join(noSitePackages, "lib", "python3.11"), { recursive: true });
  expect(getSitePackagesDir(noSitePackages)).toBeNull();

  const fileSitePackages = join(project, "file-site-packages");
  mkdirSync(join(fileSitePackages, "Lib"), { recursive: true });
  writeFileSync(join(fileSitePackages, "Lib", "site-packages"), "not a directory");
  expect(getSitePackagesDir(fileSitePackages)).toBeNull();

  expect(getSitePackagesDir(tempDir())).toBeNull();
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

  test("covers copy installs, target selection, overwrite guards, and helper fallbacks", () => {
    const root = tempDir();
    const source = writeSkill(join(root, "source", "agent"), "agent", "Agent skill.");
    const targetDir = join(root, ".agents", "skills");
    const skill = makeSkill({ name: "agent", skillDir: source });

    expect(getTargetDirs(root, { includeClaude: true })).toEqual([
      { name: "universal", path: join(root, ".agents", "skills") },
      { name: "claude-compatible", path: join(root, ".claude", "skills") },
    ]);

    const copied = installSkill(skill, targetDir, { copy: true });
    expect(lstatSync(copied).isDirectory()).toBe(true);
    expect(readFileSync(join(copied, "SKILL.md"), "utf8")).toContain("Agent skill.");
    expect(listInstalledSkills(targetDir)).toMatchObject([
      { name: "agent", type: "directory", target: null, hasSkillMd: true },
    ]);
    expect(uninstallSkill("agent", targetDir)).toBe(false);

    rmSync(copied, { recursive: true });
    mkdirSync(targetDir, { recursive: true });
    writeFileSync(join(targetDir, "agent"), "");
    expect(() => installSkill(skill, targetDir)).toThrow("Cannot overwrite non-symlink file");
    unlinkSync(join(targetDir, "agent"));
    writeFileSync(join(targetDir, "ignored.txt"), "");
    expect(listInstalledSkills(targetDir)).toEqual([]);

    const targetFile = join(tempDir(), "skills-file");
    writeFileSync(targetFile, "not a directory");
    expect(listInstalledSkills(targetFile)).toEqual([]);

    execFileSync("mkfifo", [join(targetDir, "agent")]);
    expect(() => installSkill(skill, targetDir)).toThrow();
    rmSync(join(targetDir, "agent"));

    expect(installerTesting.getSymlinkTarget({ source: root, dest: join(root, "agent") })).toBe(
      root,
    );
    expect(installerTesting.resolveSymlink(join(root, "missing"))).toBeNull();
    expect(installerTesting.isSymlink(join(root, "missing"))).toBe(false);
    expect(installerTesting.isDirectory(join(root, "missing"))).toBe(false);
  });
});

test("CLI scan defaults to top-level project dependencies", async () => {
  const project = writeProjectWithTopLevelAndTransitiveSkills();
  mkdirSync(join(project, "node_modules"), { recursive: true });
  writeNodePackageSkill({
    nodeModules: join(project, "node_modules"),
    packageName: "@scope/node-pkg",
    skillName: "node-skill",
  });
  writeNodePackageSkill({
    nodeModules: join(project, "node_modules"),
    packageName: "transitive-node-pkg",
    skillName: "transitive-node-skill",
  });
  writeFileSync(
    join(project, "package.json"),
    JSON.stringify({ dependencies: { "@scope/node-pkg": "^1.0.0" } }),
  );
  process.chdir(project);
  const log = vi.spyOn(console, "log").mockImplementation(() => undefined);
  vi.spyOn(console, "error").mockImplementation(() => undefined);

  await createProgram().parseAsync(["node", "library-skills", "scan"]);

  expect(log).toHaveBeenCalledWith("Target Python environment: .venv");
  expect(log).toHaveBeenCalledWith(
    expect.stringMatching(/^Site-packages: \.venv[/\\]/),
  );
  expect(log).toHaveBeenCalledWith("node_modules: node_modules");
  expect(log).toHaveBeenCalledWith(expect.stringContaining("Skill"));
  expect(log).toHaveBeenCalledWith(expect.stringContaining("top-skill"));
  expect(log).toHaveBeenCalledWith(expect.stringContaining("top-level-pkg"));
  expect(log).toHaveBeenCalledWith(expect.stringContaining("node-skill"));
  expect(log).toHaveBeenCalledWith(expect.stringContaining("@scope/node-pkg"));
  expect(log).not.toHaveBeenCalledWith(expect.stringContaining("transitive-node-skill"));
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

test("CLI helpers filter skills and classify installed statuses", () => {
  const root = tempDir();
  const target = { name: "universal", path: join(root, ".agents", "skills") };
  mkdirSync(target.path, { recursive: true });
  const up = makeSkill({ name: "up", skillDir: writeSkill(join(root, "src", "up"), "up", "Up.") });
  const real = makeSkill({
    name: "real",
    skillDir: writeSkill(join(root, "src", "real"), "real", "Real."),
  });
  const outdated = makeSkill({
    name: "outdated",
    skillDir: writeSkill(join(root, "src", "outdated-new"), "outdated", "Outdated."),
  });
  const broken = makeSkill({
    name: "broken",
    skillDir: writeSkill(join(root, "src", "broken"), "broken", "Broken."),
  });
  const newSkill = makeSkill({
    name: "new",
    skillDir: writeSkill(join(root, "src", "new"), "new", "New."),
  });
  const old = writeSkill(join(root, "old"), "old", "Old.");

  symlinkSync(up.skillDir, join(target.path, "up"));
  symlinkSync(real.skillDir, join(target.path, "alias"));
  symlinkSync(old, join(target.path, "outdated"));
  symlinkSync(old, join(target.path, "orphan"));
  symlinkSync(join(root, "missing"), join(target.path, "broken"));
  writeSkill(join(target.path, "manual"), "manual", "Manual.");

  const statuses = cliTesting.installedStatuses({
    targets: [target],
    skills: [up, real, outdated, broken, newSkill],
  });
  const statusByName = new Map(statuses.map((status) => [status.name, status.status]));

  expect(statusByName.get("up")).toBe("up to date");
  expect(statusByName.get("alias")).toBe("name mismatch");
  expect(statusByName.get("outdated")).toBe("outdated");
  expect(statusByName.get("orphan")).toBe("orphaned");
  expect(statusByName.get("broken")).toBe("broken");
  expect(statusByName.get("manual")).toBe("hand-authored");
  expect(statusByName.get("new")).toBe("new");

  expect(
    cliTesting.filterInstallableSkills({
      skills: [up, makeSkill({ name: "up", skillDir: real.skillDir })],
      selectedNames: [],
      includeAll: true,
    }),
  ).toEqual([]);
  expect(
    cliTesting.filterInstallableSkills({
      skills: [up, real],
      selectedNames: ["real"],
      includeAll: false,
    }),
  ).toEqual([real]);
  expect(cliTesting.findCollisions([up, real, makeSkill({ name: "up", skillDir: up.skillDir })])).toEqual(
    new Set(["up"]),
  );
  expect(cliTesting.displayPath(join(root, ".agents", "skills", "up"), root)).toBe(
    join(".agents", "skills", "up"),
  );
  expect(cliTesting.displayPath(root, root)).toBe(".");
  expect(cliTesting.displayPath(join(tempDir(), "outside"), root)).toMatch(/outside$/);
  expect(cliTesting.displayPath(null, root)).toBe("");
  const log = vi.spyOn(console, "log").mockImplementation(() => undefined);
  cliTesting.printTable(["Name", "Value"], [{ Name: "demo", Value: "ok" }]);
  expect(log.mock.calls.map((call) => call[0])).toEqual([
    "Name  Value",
    "----  -----",
    "demo  ok   ",
  ]);
});

test("CLI list and scan commands cover JSON, installed, warnings, and empty output", async () => {
  const project = writeProjectWithTopLevelAndTransitiveSkills();
  process.chdir(project);
  const { log } = mockConsole();

  await main(["node", "library-skills", "scan", "--all"]);
  expect(log).toHaveBeenCalledWith(expect.stringContaining("transitive-skill"));

  await createProgram().parseAsync(["node", "library-skills", "list", "--json", "--all"]);
  const json = JSON.parse(String(log.mock.calls.at(-1)?.[0]));
  expect(json.project_root).toBe(project);
  expect(json.skills.map((skill: { name: string }) => skill.name)).toEqual([
    "top-skill",
    "transitive-skill",
  ]);

  await createProgram().parseAsync(["node", "library-skills", "install", "--yes", "--all"]);
  await createProgram().parseAsync(["node", "library-skills", "list", "--json", "--all"]);
  const installedJson = JSON.parse(String(log.mock.calls.at(-1)?.[0]));
  expect(installedJson.installed.map((status: { name: string }) => status.name)).toEqual([
    "top-skill",
    "transitive-skill",
  ]);

  await createProgram().parseAsync(["node", "library-skills", "list", "--installed"]);
  expect(log).toHaveBeenCalledWith(expect.stringContaining("top-skill"));
  expect(log).toHaveBeenCalledWith(
    expect.stringContaining(join(".agents", "skills", "top-skill")),
  );

  await createProgram().parseAsync(["node", "library-skills", "list", "--all"]);
  expect(log).toHaveBeenCalledWith(expect.stringContaining("transitive-skill"));

  const emptyInstalled = tempDir();
  process.chdir(emptyInstalled);
  writeFileSync(join(emptyInstalled, "pyproject.toml"), "[project]\nname = 'empty'\n");
  await createProgram().parseAsync(["node", "library-skills", "list", "--installed"]);
  expect(log).toHaveBeenCalledWith("No skills installed.");

  process.chdir(project);
  rmSync(join(project, ".venv"), { recursive: true, force: true });
  await createProgram().parseAsync(["node", "library-skills", "list", "--json"]);
  const noEnvJson = JSON.parse(String(log.mock.calls.at(-1)?.[0]));
  expect(noEnvJson.target_environment).toBe("");
  expect(noEnvJson.node_modules).toBe("");

  await createProgram().parseAsync(["node", "library-skills", "scan"]);
  expect(log).toHaveBeenCalledWith(
    expect.stringContaining(
      "No target Python environment with site-packages or node_modules was found.",
    ),
  );
  expect(log).toHaveBeenCalledWith("No skills found in installed packages.");
});

test("CLI install command covers interactive, copy, selected, and skipped installs", async () => {
  const project = writeProjectWithTopLevelAndTransitiveSkills();
  process.chdir(project);
  const { log } = mockConsole();

  vi.mocked(checkbox).mockResolvedValueOnce([]);
  await createProgram().parseAsync(["node", "library-skills", "install"]);
  expect(log).toHaveBeenCalledWith("No skills selected.");

  await createProgram().parseAsync([
    "node",
    "library-skills",
    "install",
    "--yes",
    "-s",
    "top-skill",
    "--skill",
    "transitive-skill",
    "--copy",
    "--claude",
  ]);
  expect(lstatSync(join(project, ".agents", "skills", "top-skill")).isDirectory()).toBe(true);
  expect(lstatSync(join(project, ".claude", "skills", "transitive-skill")).isDirectory()).toBe(true);

  await createProgram().parseAsync(["node", "library-skills", "install", "--yes", "--all"]);
  expect(log).toHaveBeenCalledWith(expect.stringContaining("Skipped top-skill"));

  expect(() =>
    cliTesting.installSelected({
      skills: [makeSkill({ name: "missing-source", skillDir: join(project, "missing") })],
      targets: [{ name: "universal", path: join(project, "other-skills") }],
      projectRoot: project,
      copy: true,
    }),
  ).toThrow();
});

test("CLI remove command covers selected, interactive, and empty removals", async () => {
  const project = writeProjectWithTopLevelAndTransitiveSkills();
  process.chdir(project);
  const { log } = mockConsole();

  await createProgram().parseAsync(["node", "library-skills", "install", "--yes", "--all"]);
  await createProgram().parseAsync(["node", "library-skills", "remove", "top-skill"]);
  expect(log).toHaveBeenCalledWith("Removed: top-skill (universal)");

  vi.mocked(checkbox).mockImplementationOnce(async (prompt) => {
    const choice = prompt.choices[0].value;
    unlinkSync(choice.path);
    return [choice];
  });
  await createProgram().parseAsync(["node", "library-skills", "remove"]);
  expect(log).toHaveBeenCalledWith("Not found: transitive-skill (universal)");

  vi.mocked(checkbox).mockResolvedValueOnce([]);
  await createProgram().parseAsync(["node", "library-skills", "remove"]);
  expect(log).toHaveBeenCalledWith("No skills selected.");

  await createProgram().parseAsync(["node", "library-skills", "remove", "--yes"]);
  expect(log).toHaveBeenCalledWith("No skills selected.");
});

test("CLI sync covers check mode, interactive installs, and automatic drift repair", async () => {
  const project = writeProjectWithTopLevelAndTransitiveSkills();
  process.chdir(project);
  const { log } = mockConsole();

  await cliTesting.sync({ all: true });
  expect(lstatSync(join(project, ".agents", "skills", "top-skill")).isSymbolicLink()).toBe(true);
  expect(log).toHaveBeenCalledWith("Installed 2 skill target(s).");

  unlinkSync(join(project, ".agents", "skills", "top-skill"));
  symlinkSync(join(project, "missing"), join(project, ".agents", "skills", "top-skill"));
  unlinkSync(join(project, ".agents", "skills", "transitive-skill"));
  symlinkSync(
    writeSkill(join(project, "old-transitive"), "transitive-skill", "Old transitive."),
    join(project, ".agents", "skills", "transitive-skill"),
  );
  await cliTesting.sync({ all: true });

  unlinkSync(join(project, ".agents", "skills", "top-skill"));
  symlinkSync(join(project, "missing"), join(project, ".agents", "skills", "top-skill"));
  unlinkSync(join(project, ".agents", "skills", "transitive-skill"));
  symlinkSync(
    writeSkill(join(project, "old-transitive-again"), "transitive-skill", "Old transitive."),
    join(project, ".agents", "skills", "transitive-skill"),
  );
  await cliTesting.sync({ yes: true, all: true, check: true });
  expect(process.exitCode).toBe(1);
  process.exitCode = undefined;

  await cliTesting.sync({ yes: true, all: true });
  expect(existsSync(join(project, ".agents", "skills", "top-skill", "SKILL.md"))).toBe(true);
  expect(log).toHaveBeenCalledWith(expect.stringContaining("top-skill"));

  const empty = tempDir();
  process.chdir(empty);
  await cliTesting.sync({ yes: true });
  expect(log).toHaveBeenCalledWith("No installed or discovered skills found.");

  await cliTesting.sync({ yes: true, check: true });
  expect(process.exitCode).toBeUndefined();

  const interactive = tempDir();
  const interactiveSitePackages = join(interactive, ".venv", "lib", "python3.12", "site-packages");
  mkdirSync(interactiveSitePackages, { recursive: true });
  writeFileSync(join(interactive, ".venv", "pyvenv.cfg"), "");
  writePackageSkill({
    sitePackages: interactiveSitePackages,
    packageDir: "interactive_pkg",
    skillName: "interactive-skill",
    packageName: "interactive-pkg",
  });
  process.chdir(interactive);
  vi.mocked(checkbox).mockImplementationOnce(async (prompt) => [prompt.choices[0].value]);
  await cliTesting.sync({});
  expect(lstatSync(join(interactive, ".agents", "skills", "interactive-skill")).isSymbolicLink()).toBe(
    true,
  );

  process.chdir(project);
  await createProgram().parseAsync(["--all"], { from: "user" });
  expect(log).toHaveBeenCalledWith("Installed 2 skill target(s).");
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

function writeRawSkill(directory: string, contents: string): string {
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, "SKILL.md"), contents);
  return directory;
}

function mockConsole(): {
  log: ReturnType<typeof vi.spyOn>;
  error: ReturnType<typeof vi.spyOn>;
  table: ReturnType<typeof vi.spyOn>;
} {
  return {
    log: vi.spyOn(console, "log").mockImplementation(() => undefined),
    error: vi.spyOn(console, "error").mockImplementation(() => undefined),
    table: vi.spyOn(console, "table").mockImplementation(() => undefined),
  };
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

function writeNodePackageSkill({
  nodeModules,
  packageName,
  skillName,
  version = "1.0.0",
}: {
  nodeModules: string;
  packageName: string;
  skillName: string;
  version?: string;
}): void {
  const packageRoot = join(nodeModules, packageName);
  mkdirSync(packageRoot, { recursive: true });
  writeFileSync(
    join(packageRoot, "package.json"),
    JSON.stringify({ name: packageName, version }),
  );
  writeSkill(
    join(packageRoot, ".agents", "skills", skillName),
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
