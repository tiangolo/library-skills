import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parse, type TomlTable } from "smol-toml";
import { normalizePackageName } from "./scanner.js";

export function getPythonTopLevelDeps(projectRoot: string): Set<string> | null {
	const pyproject = join(projectRoot, "pyproject.toml");
	if (!existsSync(pyproject)) {
		return null;
	}
	return getPythonTopLevelDepsFromFiles([pyproject]);
}

export function getPythonTopLevelDepsFromFiles(
	pyprojects: string[],
): Set<string> | null {
	if (pyprojects.length === 0) {
		return null;
	}

	const deps = new Set<string>();
	let found = false;
	for (const pyproject of pyprojects) {
		if (!existsSync(pyproject)) {
			continue;
		}
		let data: TomlTable;
		try {
			data = parse(readFileSync(pyproject, "utf8"));
		} catch {
			return null;
		}
		found = true;
		extractPythonTopLevelDeps(data, deps);
	}
	return found ? deps : null;
}

function extractPythonTopLevelDeps(data: TomlTable, deps: Set<string>): void {
	const project = data["project"];
	if (isRecord(project)) {
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
	}

	const dependencyGroups = data["dependency-groups"];
	if (isRecord(dependencyGroups)) {
		for (const groupName of Object.keys(dependencyGroups)) {
			extractDepsFromDependencyGroup(groupName, dependencyGroups, deps, new Set());
		}
	}
}

export function getNodeTopLevelDeps(projectRoot: string): Set<string> | null {
	const packageJson = join(projectRoot, "package.json");
	if (!existsSync(packageJson)) {
		return null;
	}

	return getNodeTopLevelDepsFromFiles([packageJson]);
}

export function getNodeTopLevelDepsFromFiles(
	packageJsonFiles: string[],
): Set<string> | null {
	if (packageJsonFiles.length === 0) {
		return null;
	}

	const deps = new Set<string>();
	let found = false;
	for (const packageJson of packageJsonFiles) {
		if (!existsSync(packageJson)) {
			continue;
		}
		const data = readPackageJson(packageJson);
		if (data === null) {
			return null;
		}
		found = true;
		extractNodeTopLevelDeps(data, deps);
	}

	return found ? deps : null;
}

function readPackageJson(packageJson: string): Record<string, unknown> | null {
	let data: unknown;
	try {
		data = JSON.parse(readFileSync(packageJson, "utf8"));
	} catch {
		return null;
	}

	if (!isRecord(data)) {
		return {};
	}

	return data;
}

function extractNodeTopLevelDeps(
	data: Record<string, unknown>,
	deps: Set<string>,
): void {
	for (const field of [
		"dependencies",
		"devDependencies",
		"optionalDependencies",
		"peerDependencies",
	]) {
		const dependencies = data[field];
		if (!isRecord(dependencies)) {
			continue;
		}
		for (const packageName of Object.keys(dependencies)) {
			deps.add(normalizePackageName(packageName));
		}
	}
}

export function getTopLevelDeps(projectRoot: string): Set<string> | null {
	const dependencySets = [
		getPythonTopLevelDeps(projectRoot),
		getNodeTopLevelDeps(projectRoot),
	].filter((deps): deps is Set<string> => deps !== null);
	if (dependencySets.length === 0) {
		return null;
	}
	return new Set(dependencySets.flatMap((deps) => [...deps]));
}

export function getWorkspaceTopLevelDeps(pyprojects: string[]): Set<string> | null {
	return getPythonTopLevelDepsFromFiles(pyprojects);
}

export function getNodeWorkspaceTopLevelDeps(
	packageJsonFiles: string[],
): Set<string> | null {
	return getNodeTopLevelDepsFromFiles(packageJsonFiles);
}

function extractDepsFromSpecs(depSpecs: unknown[], deps: Set<string>): void {
	for (const depSpec of depSpecs) {
		if (typeof depSpec !== "string") {
			continue;
		}
		const packageName = depSpec.split(/[~>=<![\];,\s]/)[0]?.trim();
		if (packageName && !packageName.startsWith("#")) {
			deps.add(normalizePackageName(packageName));
		}
	}
}

function extractDepsFromDependencyGroup(
  groupName: unknown,
  dependencyGroups: Record<string, unknown>,
  deps: Set<string>,
  visited: Set<unknown>,
): void {
	if (visited.has(groupName)) {
		return;
	}
	visited.add(groupName);

	if (typeof groupName !== "string") {
		return;
	}

	const groupDependencies = dependencyGroups[groupName];
	if (!Array.isArray(groupDependencies)) {
		return;
	}

	extractDepsFromSpecs(groupDependencies, deps);
	for (const groupDependency of groupDependencies) {
		if (!isRecord(groupDependency)) {
			continue;
		}
		extractDepsFromDependencyGroup(
			groupDependency["include-group"],
			dependencyGroups,
			deps,
			visited,
		);
	}
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const testing = {
	extractDepsFromSpecs,
	extractDepsFromDependencyGroup,
	isRecord,
};
