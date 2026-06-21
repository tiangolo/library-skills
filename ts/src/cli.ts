#!/usr/bin/env node

import checkbox from "@inquirer/checkbox";
import { Command } from "commander";
import { realpathSync, readFileSync, statSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
	getNodeWorkspaceTopLevelDeps,
	getTopLevelDeps,
	getWorkspaceTopLevelDeps,
} from "./deps.js";
import {
	getAllTargetDirs,
	getDefaultInstallTargetDirs,
	getExistingTargetDirs,
	getTargetDirs,
	inspectToolSkill,
	installSkill,
	installToolSkill,
	InstallError,
	listInstalledSkills,
	TOOL_SKILL_MARKER,
	TOOL_SKILL_NAME,
	ToolSkillError,
	uninstallSkill,
	type InstallTarget,
	type ToolSkillStatus,
} from "./installer.js";
import {
	findNodeModules,
	findProjectRoot,
	findVenv,
	getSitePackagesDir,
} from "./python-env.js";
import {
	normalizePackageName,
	scanNodePackages,
	scanPythonDistributions,
	type ScanResult,
	type Skill,
} from "./scanner.js";
import {
	findNodeWorkspace,
	findUvWorkspace,
	nodeWorkspaceDependencyFiles,
	workspaceDependencyFiles,
	type NodeWorkspace,
	type UvWorkspace,
} from "./workspace.js";

interface ProjectContext {
	cwd: string;
	projectRoot: string;
	targetEnvironment: string | null;
	sitePackagesDir: string | null;
	nodeModulesDir: string | null;
	workspace: UvWorkspace | null;
	nodeWorkspace: NodeWorkspace | null;
	workspaceDependencyFiles: string[];
	nodeWorkspaceDependencyFiles: string[];
	dependencyFiles: string[];
}

interface InstalledStatus {
	target: InstallTarget;
	name: string;
	type: "symlink" | "directory" | "missing";
	path: string;
	targetPath: string | null;
	status:
		| "up to date"
		| "broken"
		| "outdated"
		| "orphaned"
		| "name mismatch"
		| "hand-authored"
		| "new";
	skill: Skill | null;
}

interface GlobalOptions {
	claude?: boolean;
	yes?: boolean;
	check?: boolean;
	all?: boolean;
	skill?: string[];
	copy?: boolean;
	toolSkill?: boolean;
}

interface InstallOptions {
	claude?: boolean;
	yes?: boolean;
	all?: boolean;
	skill?: string[];
	copy?: boolean;
}

interface ListOptions {
	installed?: boolean;
	json?: boolean;
	claude?: boolean;
	all?: boolean;
}

interface ScanOptions {
	all?: boolean;
	json?: boolean;
}

const ACTION_COLORS = {
	install: "\u001b[1;32m",
	repair: "\u001b[1;34m",
	remove: "\u001b[1;31m",
	reset: "\u001b[0m",
} as const;

function printActionHeader(action: "install" | "repair" | "remove"): void {
	const labels = {
		install: "Install new skills",
		repair: "Repair installed skills",
		remove: "Remove stale skills",
	};
	console.log(`${ACTION_COLORS[action]}${labels[action]}${ACTION_COLORS.reset}`);
}

function getProjectContext(cwd = process.cwd()): ProjectContext {
	const workspace = findUvWorkspace(cwd);
	const nodeWorkspace = findNodeWorkspace(cwd);
	const projectRoot = workspace?.root ?? nodeWorkspace?.root ?? findProjectRoot(cwd) ?? cwd;
	const workspaceFiles =
		workspace === null ? [] : workspaceDependencyFiles(workspace);
	const nodeWorkspaceFiles =
		nodeWorkspace === null ? [] : nodeWorkspaceDependencyFiles(nodeWorkspace);
	const targetEnvironment = findVenv(cwd);
	const sitePackagesDir =
		targetEnvironment === null ? null : getSitePackagesDir(targetEnvironment);
	const nodeModulesDir = findNodeModules(cwd);
	return {
		cwd,
		projectRoot,
		targetEnvironment,
		sitePackagesDir,
		nodeModulesDir,
		workspace,
		nodeWorkspace,
		workspaceDependencyFiles: workspaceFiles,
		nodeWorkspaceDependencyFiles: nodeWorkspaceFiles,
		dependencyFiles: [...workspaceFiles, ...nodeWorkspaceFiles],
	};
}

function scanContext(context: ProjectContext): ScanResult {
	const result: ScanResult = {
		skills: [],
		warnings: [],
		environmentPath: context.targetEnvironment ?? undefined,
	};
	if (context.sitePackagesDir !== null) {
		const pythonResult = scanPythonDistributions(context.sitePackagesDir);
		result.skills.push(...pythonResult.skills);
		result.warnings.push(...pythonResult.warnings);
	}
	if (context.workspace?.currentMember) {
		const memberVenv = `${context.workspace.currentMember}/.venv`;
		if (exists(memberVenv)) {
			result.warnings.push(
				`Ignoring member-local .venv in uv workspace: ${memberVenv}`,
			);
		}
	}
	if (context.nodeModulesDir !== null) {
		const nodeResult = scanNodePackages(context.nodeModulesDir);
		result.skills.push(...nodeResult.skills);
		result.warnings.push(...nodeResult.warnings);
	}
	if (context.sitePackagesDir === null && context.nodeModulesDir === null) {
		result.warnings.push(
			"No target Python environment with site-packages or node_modules was " +
				"found. Run from a project root after installing dependencies, for " +
				"example with 'uv sync' for Python or 'npm install' for Node.js.",
		);
	}
	return result;
}

function topLevelSkills({
	context,
	skills,
	includeAll,
}: {
	context: ProjectContext;
	skills: Skill[];
	includeAll: boolean;
}): Skill[] {
	if (includeAll) {
		return skills;
	}
	const topLevelDeps = getTopLevelDeps(context.projectRoot);
	const workspaceTopLevelDeps = getWorkspaceTopLevelDepsForContext(context);
	const selectedTopLevelDeps =
		context.workspace === null && context.nodeWorkspace === null
			? topLevelDeps
			: workspaceTopLevelDeps;
	if (selectedTopLevelDeps === null) {
		return skills;
	}
	return skills.filter((skill) =>
		selectedTopLevelDeps.has(normalizePackageName(skill.packageName)),
	);
}

function getWorkspaceTopLevelDepsForContext(
	context: ProjectContext,
): Set<string> | null {
	const dependencySets = [
		context.workspace === null
			? null
			: getWorkspaceTopLevelDeps(context.workspaceDependencyFiles),
		context.nodeWorkspace === null
			? null
			: getNodeWorkspaceTopLevelDeps(context.nodeWorkspaceDependencyFiles),
	].filter((deps): deps is Set<string> => deps !== null);
	if (dependencySets.length === 0) {
		return null;
	}
	return new Set(dependencySets.flatMap((deps) => [...deps]));
}

function printWarnings(warnings: string[]): void {
	for (const warning of warnings) {
		console.log(`Warning: ${warning}`);
	}
}

function displayPath(path: string | null | undefined, projectRoot: string): string {
	if (!path) {
		return "";
	}
	const relativePath = relative(resolve(projectRoot), resolve(path));
	if (relativePath === "") {
		return ".";
	}
	if (!relativePath.startsWith("..") && !isAbsolute(relativePath)) {
		return relativePath;
	}
	return path;
}

function printContext(context: ProjectContext): void {
	console.log(`Project root: ${context.projectRoot}`);
	if (context.workspace !== null) {
		console.log(`Workspace root: ${context.workspace.root}`);
		if (context.workspace.currentMember !== null) {
			console.log(`Workspace member: ${context.workspace.currentMember}`);
		}
	} else if (context.nodeWorkspace !== null) {
		console.log(`Workspace root: ${context.nodeWorkspace.root}`);
		if (context.nodeWorkspace.currentMember !== null) {
			console.log(`Workspace member: ${context.nodeWorkspace.currentMember}`);
		}
	}
	console.log(
		`Target Python environment: ${
			context.targetEnvironment
				? displayPath(context.targetEnvironment, context.projectRoot)
				: "not found"
		}`,
	);
	if (context.sitePackagesDir) {
		console.log(
			`Site-packages: ${displayPath(
				context.sitePackagesDir,
				context.projectRoot,
			)}`,
		);
	}
	if (context.nodeModulesDir) {
		console.log(
			`node_modules: ${displayPath(context.nodeModulesDir, context.projectRoot)}`,
		);
	}
}

function printSkills(skills: Skill[]): void {
	if (skills.length === 0) {
		console.log("No skills found in installed packages.");
		return;
	}
	printTable(
		["Skill", "Package", "Version", "Description"],
		skills.map((skill) => ({
			Skill: skill.name,
			Package: skill.packageName,
			Version: skill.packageVersion,
			Description: skill.description,
		})),
	);
}

function scanJsonPayload({
	context,
	skills,
	result,
}: {
	context: ProjectContext;
	skills: Skill[];
	result: ScanResult;
}): Record<string, unknown> {
	return {
			project_root: context.projectRoot,
			workspace_root: context.workspace?.root ?? context.nodeWorkspace?.root ?? "",
			workspace_member:
				context.workspace?.currentMember ??
				context.nodeWorkspace?.currentMember ??
				"",
		dependency_files: context.dependencyFiles,
		target_environment: context.targetEnvironment ?? "",
		node_modules: context.nodeModulesDir ?? "",
		skills: skills.map((skill) => ({
			name: skill.name,
			description: skill.description,
			package: skill.packageName,
			version: skill.packageVersion,
			path: skill.skillDir,
		})),
		warnings: result.warnings,
	};
}

function printTable(
	columns: string[],
	rows: Array<Record<string, string>>,
): void {
	const widths = columns.map((column) =>
		Math.max(column.length, ...rows.map((row) => row[column].length)),
	);
	const formatRow = (row: Record<string, string>) =>
		columns
			.map((column, index) => row[column].padEnd(widths[index]))
			.join("  ");

	console.log(formatRow(Object.fromEntries(columns.map((column) => [column, column]))));
	console.log(widths.map((width) => "-".repeat(width)).join("  "));
	for (const row of rows) {
		console.log(formatRow(row));
	}
}

function findCollisions(skills: Skill[]): Set<string> {
	const counts = new Map<string, number>();
	for (const skill of skills) {
		counts.set(skill.name, (counts.get(skill.name) ?? 0) + 1);
	}
	return new Set(
		[...counts.entries()]
			.filter(([, count]) => count > 1)
			.map(([name]) => name),
	);
}

function deduplicateSkills(skills: Skill[]): Skill[] {
	const seen = new Set<string>();
	const unique: Skill[] = [];
	for (const skill of skills) {
		const key = resolve(skill.skillDir);
		if (seen.has(key)) {
			continue;
		}
		seen.add(key);
		unique.push(skill);
	}
	return unique;
}

function filterInstallableSkills({
	skills,
	selectedNames,
	includeAll,
}: {
	skills: Skill[];
	selectedNames: string[];
	includeAll: boolean;
}): Skill[] {
	const collisions = findCollisions(skills);
	if (collisions.size > 0) {
		console.log(
			`Skipping colliding skill names: ${[...collisions].sort().join(", ")}`,
		);
	}

	const installable = skills.filter((skill) => !collisions.has(skill.name));
	if (selectedNames.length > 0) {
		const selected = new Set(selectedNames);
		return installable.filter((skill) => selected.has(skill.name));
	}
	return includeAll ? installable : [];
}

function installedStatuses({
	targets,
	skills,
}: {
	targets: InstallTarget[];
	skills: Skill[];
}): InstalledStatus[] {
	const skillsByDir = new Map(
		skills.map((skill) => [resolve(skill.skillDir), skill]),
	);
	const skillsByName = new Map(skills.map((skill) => [skill.name, skill]));
	const statuses: InstalledStatus[] = [];

	for (const target of targets) {
		for (const installed of listInstalledSkills(target.path)) {
			if (
				installed.name === TOOL_SKILL_NAME &&
				exists(`${installed.path}/${TOOL_SKILL_MARKER}`)
			) {
				continue;
			}
			const skill = installed.target
				? skillsByDir.get(resolve(installed.target))
				: null;
			let matchedSkill = skill ?? null;
			let status: InstalledStatus["status"] = "hand-authored";

			if (installed.type === "symlink") {
				if (installed.target === null || !exists(installed.target)) {
					status = "broken";
					matchedSkill = skillsByName.get(installed.name) ?? null;
				} else if (skill) {
					status =
						installed.name === skill.name ? "up to date" : "name mismatch";
				} else if (skillsByName.has(installed.name)) {
					matchedSkill = skillsByName.get(installed.name) ?? null;
					status = "outdated";
				} else {
					status = "orphaned";
				}
			}

			statuses.push({
				target,
				name: installed.name,
				type: installed.type,
				path: installed.path,
				targetPath: installed.target,
				status,
				skill: matchedSkill,
			});
		}
	}

	const installedNames = new Set(
		statuses
			.filter((status) =>
				["up to date", "outdated", "broken", "name mismatch"].includes(
					status.status,
				),
			)
			.map((status) => `${status.target.name}\0${status.name}`),
	);
	for (const target of targets) {
		for (const skill of skills) {
			if (!installedNames.has(`${target.name}\0${skill.name}`)) {
				statuses.push({
					target,
					name: skill.name,
					type: "missing",
					path: `${target.path}/${skill.name}`,
					targetPath: skill.skillDir,
					status: "new",
					skill,
				});
			}
		}
	}
	return statuses;
}

function printStatusTable(statuses: InstalledStatus[], projectRoot: string): void {
	printTable(
		["Target", "Skill", "Status", "Path", "Source"],
		statuses.map((status) => ({
			Target: status.target.name,
			Skill: status.name,
			Status: status.status,
			Path: displayPath(status.path, projectRoot),
			Source: displayPath(status.targetPath, projectRoot),
		})),
	);
}

function printToolSkillStatusTable(
	statuses: ToolSkillStatus[],
	projectRoot: string,
): void {
	printTable(
		["Target", "Status", "Path"],
		statuses.map((status) => ({
			Target: status.target.name,
			Status: status.status,
			Path: displayPath(status.path, projectRoot),
		})),
	);
}

function printInstalledSkillsTable(
	statuses: InstalledStatus[],
	projectRoot: string,
): void {
	const installed = statuses.filter((status) => status.type !== "missing");
	if (installed.length === 0) {
		console.log("No skills installed.");
		return;
	}
	printStatusTable(installed, projectRoot);
}

async function selectSkillsInteractive(skills: Skill[]): Promise<Skill[]> {
	printActionHeader("install");
	return checkbox<Skill>({
		message: "Select skills to install (press Space to select, Enter to confirm):",
		choices: skills.map((skill) => ({
			name: `${skill.name} (${skill.packageName})`,
			value: skill,
		})),
	});
}

async function selectTargetsInteractive({
	projectRoot,
	defaultTargets,
}: {
	projectRoot: string;
	defaultTargets: InstallTarget[];
}): Promise<InstallTarget[]> {
	const defaultNames = new Set(defaultTargets.map((target) => target.name));
	return checkbox<InstallTarget>({
		message:
			"Select installation targets (press Space to select, Enter to confirm):",
		choices: getAllTargetDirs(projectRoot).map((target) => ({
			name: displayPath(target.path, projectRoot),
			value: target,
			checked: defaultNames.has(target.name),
		})),
		validate: (selected) =>
			selected.length > 0 || "Please select at least one installation target.",
	});
}

async function selectInstallTargets({
	projectRoot,
	includeClaude,
	interactive,
}: {
	projectRoot: string;
	includeClaude?: boolean;
	interactive: boolean;
}): Promise<InstallTarget[]> {
	if (!interactive) {
		return getTargetDirs(projectRoot, { includeClaude });
	}
	return selectTargetsInteractive({
		projectRoot,
		defaultTargets: getDefaultInstallTargetDirs(projectRoot),
	});
}

async function selectToolSkillInteractive(): Promise<boolean> {
	const selected = await checkbox<boolean>({
		message:
			"Copy the Library Skills tool skill into the project so agents know how to update, repair, and check managed skills?",
		choices: [
			{
				name: "Copy Library Skills tool skill",
				value: true,
				checked: true,
			},
		],
	});
	return selected.includes(true);
}

async function selectInstalledSkillsInteractive(
	statuses: InstalledStatus[],
): Promise<InstalledStatus[]> {
	const removable = statuses.filter((status) => status.type === "symlink");
	if (removable.length === 0) {
		return [];
	}
	return checkbox<InstalledStatus>({
		message: "Select skills to remove (press Space to select, Enter to confirm):",
		choices: removable.map((status) => ({
			name: `${status.name} [${status.target.name}]`,
			value: status,
		})),
	});
}

function syncTargetDirs({
	projectRoot,
	includeClaude,
	yes,
	check,
}: {
	projectRoot: string;
	includeClaude?: boolean;
	yes?: boolean;
	check?: boolean;
}): InstallTarget[] {
	const targetsByName = new Map(
		getExistingTargetDirs(projectRoot).map((target) => [target.name, target]),
	);
	const defaultTargets =
		yes || check || includeClaude
			? getTargetDirs(projectRoot, { includeClaude })
			: getDefaultInstallTargetDirs(projectRoot);
	for (const target of defaultTargets) {
		targetsByName.set(target.name, target);
	}
	return [...targetsByName.values()];
}

function repairableStatuses(statuses: InstalledStatus[]): InstalledStatus[] {
	return statuses.filter(
		(status) =>
			status.type === "symlink" &&
			(status.status === "broken" || status.status === "outdated") &&
			status.skill !== null,
	);
}

function removableStatuses(statuses: InstalledStatus[]): InstalledStatus[] {
	return statuses.filter(
		(status) =>
			status.type === "symlink" &&
			(status.status === "orphaned" ||
				(status.status === "broken" && status.skill === null)),
	);
}

async function selectStatusesInteractive(
	statuses: InstalledStatus[],
	action: "repair" | "remove",
): Promise<InstalledStatus[]> {
	if (statuses.length === 0) {
		return [];
	}
	printActionHeader(action);
	return checkbox<InstalledStatus>({
		message: `Select skills to ${action} (press Space to select, Enter to confirm):`,
		choices: statuses.map((status) => ({
			name: `${status.name} [${status.target.name}]`,
			value: status,
			checked: true,
		})),
	});
}

function repairSelected({
	statuses,
	projectRoot,
}: {
	statuses: InstalledStatus[];
	projectRoot: string;
}): number {
	let repairedCount = 0;
	for (const status of statuses) {
		installSkill(status.skill as Skill, status.target.path);
		console.log(
			`Repaired: ${status.name} (${status.target.name}) -> ${displayPath(
				status.path,
				projectRoot,
			)}`,
		);
		repairedCount++;
	}
	return repairedCount;
}

function removeSelected({
	statuses,
	projectRoot,
}: {
	statuses: InstalledStatus[];
	projectRoot: string;
}): number {
	let removedCount = 0;
	for (const status of statuses) {
		if (uninstallSkill(status.name, status.target.path)) {
			console.log(
				`Removed ${status.status} symlink: ${status.name} (${status.target.name}) -> ${displayPath(
					status.path,
					projectRoot,
				)}`,
			);
			removedCount++;
		} else {
			console.log(`Not found: ${status.name} (${status.target.name})`);
		}
	}
	return removedCount;
}

function installSelected({
	skills,
	targets,
	projectRoot,
	copy = false,
}: {
	skills: Skill[];
	targets: InstallTarget[];
	projectRoot: string;
	copy?: boolean;
}): number {
	let installedCount = 0;
	for (const target of targets) {
		for (const skill of skills) {
			try {
				const dest = installSkill(skill, target.path, { copy });
				const method = copy ? "Copied" : "Symlinked";
				console.log(
					`${method}: ${skill.name} (${skill.packageName}) -> ${displayPath(
						dest,
						projectRoot,
					)}`,
				);
				installedCount++;
			} catch (error) {
				if (error instanceof InstallError) {
					console.log(`Skipped ${skill.name}: ${error.message}`);
				} else {
					throw error;
				}
			}
		}
	}
	return installedCount;
}

function toolSkillTargets({
	projectRoot,
	includeClaude,
}: {
	projectRoot: string;
	includeClaude?: boolean;
}): InstallTarget[] {
	return getTargetDirs(projectRoot, { includeClaude });
}

function getToolSkillTemplate(): string {
	for (const path of toolSkillTemplateCandidates()) {
		if (exists(path)) {
			return readFileSync(path, "utf-8");
		}
	}
	/* v8 ignore next -- packaged CLI should always include the bundled tool skill. */
	throw new ToolSkillError("Could not find bundled Library Skills tool skill template.");
}

function getToolSkillVersion(): string {
	const packageJsonPath = join(
		dirname(fileURLToPath(import.meta.url)),
		"..",
		"..",
		"package.json",
	);
	const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf-8")) as {
		version?: unknown;
	};
	return typeof packageJson.version === "string" ? packageJson.version : "0.0.0";
}

function toolSkillTemplateCandidates(): string[] {
	const moduleDir = dirname(fileURLToPath(import.meta.url));
	return [
		join(moduleDir, "tool_skill", "SKILL.md"),
		join(moduleDir, "..", "src", "tool_skill", "SKILL.md"),
	];
}

function syncToolSkill({
	targets,
	projectRoot,
	check,
	explicit,
}: {
	targets: InstallTarget[];
	projectRoot: string;
	check: boolean;
	explicit: boolean;
}): { changedCount: number; failed: boolean } {
	const template = getToolSkillTemplate();
	const version = getToolSkillVersion();
	const statuses = targets.map((target) => inspectToolSkill(target.path, template));
	printToolSkillStatusTable(statuses, projectRoot);

	const drift = statuses.filter(
		(status) => status.status !== "tool skill: up to date",
	);
	if (check) {
		return { changedCount: 0, failed: drift.length > 0 };
	}

	let changedCount = 0;
	let failed = false;
	for (const status of drift) {
		try {
			installToolSkill({
				targetDir: status.target.path,
				template,
				version,
			});
		} catch (error) {
			if (error instanceof ToolSkillError) {
				console.log(`Skipped tool skill: ${error.message}`);
				failed ||= explicit;
				continue;
			}
			/* v8 ignore next -- defensive rethrow for unexpected installer failures. */
			throw error;
		}
		console.log(
			`Copied: library-skills (${status.target.name}) -> ${displayPath(
				status.path,
				projectRoot,
			)}`,
		);
		changedCount++;
	}
	return { changedCount, failed };
}

async function sync(options: GlobalOptions): Promise<void> {
	const context = getProjectContext();
	const result = scanContext(context);
	let targets = syncTargetDirs({
		projectRoot: context.projectRoot,
		includeClaude: options.claude,
		yes: options.yes,
		check: options.check,
	});

	printContext(context);
	console.log();
	printWarnings(result.warnings);
	if (result.warnings.length > 0) {
		console.log();
	}

	const selectedNames = options.skill ?? [];
	const collisions = findCollisions(result.skills);
	const candidateSkills = topLevelSkills({
		context,
		skills: result.skills,
		includeAll: Boolean(options.all) || selectedNames.length > 0,
	});
	const candidateSkillNames = new Set(
		candidateSkills.map((skill) => skill.name),
	);
	const statuses = installedStatuses({
		targets,
		skills: result.skills.filter((skill) => !collisions.has(skill.name)),
	});
	const visibleStatuses = statuses.filter(
		(status) => status.status !== "new" || candidateSkillNames.has(status.name),
	);

	if (visibleStatuses.length > 0) {
		printStatusTable(visibleStatuses, context.projectRoot);
	} else {
		console.log("No installed or discovered skills found.");
	}

	const drift = statuses.filter((status) =>
		["broken", "outdated", "name mismatch", "orphaned"].includes(status.status),
	);
	if (options.check) {
		if (options.toolSkill) {
			console.log();
			const toolResult = syncToolSkill({
				targets: toolSkillTargets({
					projectRoot: context.projectRoot,
					includeClaude: options.claude,
				}),
				projectRoot: context.projectRoot,
				check: true,
				explicit: true,
			});
			if (toolResult.failed) {
				process.exitCode = 1;
			}
		}
		if (drift.length > 0 || collisions.size > 0) {
			process.exitCode = 1;
		}
		return;
	}

	const repairable = repairableStatuses(drift);
	const removable = removableStatuses(drift);
	if (drift.length > 0) {
		console.log();
		console.log("Some installed skills need attention.");
		console.log("Select the skills to install, repair, or remove.");
		console.log("Only managed symlinks will be changed.");
	}
	const selectedRepairs = options.yes
		? repairable
		: await selectStatusesInteractive(repairable, "repair");
	const selectedRemovals = options.yes
		? removable
		: await selectStatusesInteractive(removable, "remove");
	if (selectedRepairs.length > 0) {
		console.log();
		repairSelected({ statuses: selectedRepairs, projectRoot: context.projectRoot });
	}
	if (selectedRemovals.length > 0) {
		console.log();
		removeSelected({ statuses: selectedRemovals, projectRoot: context.projectRoot });
	}

	let selected = filterInstallableSkills({
		skills: candidateSkills,
		selectedNames,
		includeAll: Boolean(options.all),
	});
	if (
		selected.length === 0 &&
		!options.yes &&
		selectedNames.length === 0 &&
		!options.all &&
		options.toolSkill !== true
	) {
		const newSkills = visibleStatuses
			.filter((status) => status.status === "new" && status.skill !== null)
			.map((status) => status.skill as Skill);
		if (newSkills.length > 0) {
			selected = await selectSkillsInteractive(deduplicateSkills(newSkills));
		}
	}

	let toolSkillChanges = 0;
	let toolSkillFailed = false;
	if (selected.length > 0) {
		targets = await selectInstallTargets({
			projectRoot: context.projectRoot,
			includeClaude: options.claude,
			interactive: !options.yes && !options.claude,
		});
		if (targets.length === 0) {
			console.log("No installation targets selected.");
			return;
		}
		console.log();
		const installedCount = installSelected({
			skills: selected,
			targets,
			projectRoot: context.projectRoot,
			copy: options.copy,
		});
		console.log();
		console.log(`Installed ${installedCount} skill target(s).`);
		const shouldInstallToolSkill =
			options.toolSkill ?? (!options.yes && (await selectToolSkillInteractive()));
		if (shouldInstallToolSkill) {
			console.log();
			const toolResult = syncToolSkill({
				targets,
				projectRoot: context.projectRoot,
				check: false,
				explicit: options.toolSkill === true,
			});
			toolSkillChanges = toolResult.changedCount;
			if (toolResult.failed) {
				toolSkillFailed = true;
				process.exitCode = 1;
			}
		}
	} else if (options.toolSkill) {
		console.log();
		const toolResult = syncToolSkill({
			targets: toolSkillTargets({
				projectRoot: context.projectRoot,
				includeClaude: options.claude,
			}),
			projectRoot: context.projectRoot,
			check: false,
			explicit: true,
		});
		toolSkillChanges = toolResult.changedCount;
		if (toolResult.failed) {
			toolSkillFailed = true;
			process.exitCode = 1;
		}
	}
	if (
		selectedRepairs.length === 0 &&
		selectedRemovals.length === 0 &&
		selected.length === 0 &&
		toolSkillChanges === 0 &&
		!toolSkillFailed
	) {
		console.log("No changes needed.");
	}
}

function scanCommand(options: ScanOptions): void {
	const context = getProjectContext();
	const result = scanContext(context);
	const skills = topLevelSkills({
		context,
		skills: result.skills,
		includeAll: Boolean(options.all),
	});
	if (options.json) {
		console.log(
			JSON.stringify(scanJsonPayload({ context, skills, result }), null, 2),
		);
		return;
	}

	printContext(context);
	console.log();
	printWarnings(result.warnings);
	if (result.warnings.length > 0) {
		console.log();
	}
	printSkills(skills);
}

function listCommand(options: ListOptions): void {
	const context = getProjectContext();
	const result = scanContext(context);
	const skills = topLevelSkills({
		context,
		skills: result.skills,
		includeAll: Boolean(options.all),
	});
	const targets = getExistingTargetDirs(context.projectRoot, {
		includeClaude: options.claude,
	});
	const statuses = installedStatuses({ targets, skills: result.skills });

	if (options.json) {
		const payload = scanJsonPayload({ context, skills, result });
		console.log(
			JSON.stringify(
				{
					...payload,
					installed: statuses
						.filter((status) => status.type !== "missing")
						.map((status) => ({
							target: status.target.name,
							name: status.name,
							status: status.status,
							path: status.path,
							source: status.targetPath ?? "",
						})),
				},
				null,
				2,
			),
		);
		return;
	}

	printWarnings(result.warnings);
	if (options.installed) {
		printInstalledSkillsTable(statuses, context.projectRoot);
	} else {
		printSkills(skills);
	}
}

async function installCommand(options: InstallOptions): Promise<void> {
	const context = getProjectContext();
	const result = scanContext(context);
	const selectedNames = options.skill ?? [];
	const skills = topLevelSkills({
		context,
		skills: result.skills,
		includeAll: Boolean(options.all) || selectedNames.length > 0,
	});

	printWarnings(result.warnings);
	let selected = filterInstallableSkills({
		skills,
		selectedNames,
		includeAll: Boolean(options.all),
	});
	if (selected.length === 0 && !options.yes) {
		selected = await selectSkillsInteractive(skills);
	}

	if (selected.length === 0) {
		console.log("No skills selected.");
		return;
	}

	const targets = await selectInstallTargets({
		projectRoot: context.projectRoot,
		includeClaude: options.claude,
		interactive: !options.yes && !options.claude,
	});
	if (targets.length === 0) {
		console.log("No installation targets selected.");
		return;
	}

	const installedCount = installSelected({
		skills: selected,
		targets,
		projectRoot: context.projectRoot,
		copy: options.copy,
	});
	console.log();
	console.log(`Installed ${installedCount} skill target(s).`);
}

async function removeCommand(
	skillNames: string[],
	options: { claude?: boolean; yes?: boolean },
): Promise<void> {
	const context = getProjectContext();
	const result = scanContext(context);
	const targets = getExistingTargetDirs(context.projectRoot, {
		includeClaude: options.claude,
	});
	const statuses = installedStatuses({ targets, skills: result.skills });

	let selectedStatuses: InstalledStatus[] = [];
	if (skillNames.length > 0) {
		const selected = new Set(skillNames);
		selectedStatuses = statuses.filter(
			(status) => selected.has(status.name) && status.type === "symlink",
		);
	} else if (!options.yes) {
		selectedStatuses = await selectInstalledSkillsInteractive(statuses);
	}

	if (selectedStatuses.length === 0) {
		console.log("No skills selected.");
		return;
	}

	for (const status of selectedStatuses) {
		if (uninstallSkill(status.name, status.target.path)) {
			console.log(`Removed: ${status.name} (${status.target.name})`);
		} else {
			console.log(`Not found: ${status.name} (${status.target.name})`);
		}
	}
}

export function createProgram(): Command {
	const program = new Command().enablePositionalOptions();
	program
		.name("library-skills")
		.description(
			"Discover and reconcile agent skills from installed library packages.",
		)
		.option("--claude", "Also manage .claude/skills alongside .agents/skills")
		.option("-y, --yes", "Skip confirmation prompts")
		.option("--check", "Validate only; exit 1 if installs drift")
		.option("--all", "Install all newly discovered unmanaged skills")
		.option("--copy", "Copy files instead of creating symlinks")
		.option("--tool-skill", "Copy the Library Skills tool skill into the project")
		.option("--no-tool-skill", "Skip Library Skills tool skill management")
		.option(
			"-s, --skill <name>",
			"Install a specific discovered skill by name",
			collect,
			[],
		)
		.action(async (options: GlobalOptions) => {
			await sync(options);
		});

	program
		.command("scan")
		.description("Discover skills in installed packages.")
		.option("--json", "Output as JSON")
		.option("--all", "Include skills from transitive dependencies")
		.action((options: ScanOptions) => {
			scanCommand(options);
		});

	program
		.command("list")
		.description("List discovered or currently installed skills.")
		.option("--installed", "Only show installed skills")
		.option("--json", "Output as JSON")
		.option("--claude", "Also include .claude/skills alongside .agents/skills")
		.option("--all", "Include skills from transitive dependencies")
		.action((options: ListOptions) => {
			listCommand(options);
		});

	program
		.command("install")
		.description("Install skills from installed packages.")
		.option(
			"--claude",
			"Also install in .claude/skills alongside .agents/skills",
		)
		.option("-y, --yes", "Skip interactive selection")
		.option("--all", "Install all newly discovered unmanaged skills")
		.option(
			"-s, --skill <name>",
			"Install a specific discovered skill by name",
			collect,
			[],
		)
		.option("--copy", "Copy files instead of creating symlinks")
		.action(async (options: InstallOptions) => {
			await installCommand(options);
		});

	program
		.command("remove")
		.description("Remove installed symlinked skills.")
		.argument("[skills...]", "Names of skills to remove")
		.option(
			"--claude",
			"Also remove from .claude/skills alongside .agents/skills",
		)
		.option("-y, --yes", "Skip interactive selection")
		.action(
			async (
				skillNames: string[],
				options: { claude?: boolean; yes?: boolean },
			) => {
				await removeCommand(skillNames, options);
			},
		);

	return program;
}

export async function main(argv = process.argv): Promise<void> {
	await createProgram().parseAsync(argv);
}

function collect(value: string, previous: string[]): string[] {
	previous.push(value);
	return previous;
}

function exists(path: string): boolean {
	try {
		statSync(path);
		return true;
	} catch {
		return false;
	}
}

/* v8 ignore next 16 -- direct executable entrypoint is exercised by the packaged CLI, not in-process tests. */
if (
	process.argv[1] &&
	realpathSync(fileURLToPath(import.meta.url)) ===
		realpathSync(resolve(process.argv[1]))
) {
	main().catch((error: unknown) => {
		console.error(error);
		process.exit(1);
	});
}

export const testing = {
	filterInstallableSkills,
	findCollisions,
	getToolSkillTemplate,
	getToolSkillVersion,
	getProjectContext,
	installSelected,
	installedStatuses,
	listCommand,
	removableStatuses,
	removeSelected,
	repairSelected,
	repairableStatuses,
	scanCommand,
	selectStatusesInteractive,
	selectToolSkillInteractive,
	syncToolSkill,
	syncTargetDirs,
	sync,
	toolSkillTemplateCandidates,
	toolSkillTargets,
	topLevelSkills,
	displayPath,
	printTable,
};
