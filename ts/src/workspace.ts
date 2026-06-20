import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { relative, resolve, sep } from "node:path";
import { parse, type TomlTable } from "smol-toml";

export interface UvWorkspace {
	root: string;
	members: string[];
	currentMember: string | null;
}

export function findUvWorkspace(cwd: string): UvWorkspace | null {
	for (const directory of ancestors(cwd)) {
		const pyproject = `${directory}/pyproject.toml`;
		if (!existsSync(pyproject)) {
			continue;
		}
		const data = readPyproject(pyproject);
		if (!hasUvWorkspace(data)) {
			continue;
		}
		const members = findWorkspaceMembers(directory, data);
		return {
			root: directory,
			members,
			currentMember: findCurrentMember(cwd, members),
		};
	}
	return null;
}

export function workspaceDependencyFiles(workspace: UvWorkspace): string[] {
	if (workspace.currentMember !== null) {
		return [`${workspace.currentMember}/pyproject.toml`];
	}
	return [
		`${workspace.root}/pyproject.toml`,
		...workspace.members.map((member) => `${member}/pyproject.toml`),
	].filter((path) => existsSync(path));
}

function readPyproject(path: string): TomlTable {
	try {
		const data = parse(readFileSync(path, "utf8"));
		return isRecord(data) ? data : {};
	} catch {
		/* v8 ignore next -- covers invalid TOML or a race while reading. */
		return {};
	}
}

function hasUvWorkspace(data: TomlTable): boolean {
	const tool = data["tool"];
	if (!isRecord(tool)) {
		return false;
	}
	const uv = tool["uv"];
	if (!isRecord(uv)) {
		return false;
	}
	return isRecord(uv["workspace"]);
}

function findWorkspaceMembers(root: string, data: TomlTable): string[] {
	const workspace = getWorkspaceTable(data);
	if (workspace === null || !Array.isArray(workspace["members"])) {
		return [];
	}
	const excludes = Array.isArray(workspace["exclude"])
		? workspace["exclude"].filter(
				(value): value is string => typeof value === "string",
			)
		: [];
	const members = new Set<string>();
	for (const memberGlob of workspace["members"]) {
		if (typeof memberGlob !== "string") {
			continue;
		}
		for (const member of expandMemberGlob(root, memberGlob)) {
			const relativePath = relative(root, member).split(sep).join("/");
			if (isExcluded(relativePath, excludes)) {
				continue;
			}
			if (isFile(`${member}/pyproject.toml`)) {
				members.add(resolve(member));
			}
		}
	}
	return [...members].sort();
}

function getWorkspaceTable(data: TomlTable): Record<string, unknown> | null {
	const tool = data["tool"];
	if (!isRecord(tool)) {
		/* v8 ignore next -- guarded by hasUvWorkspace before this function is called. */
		return null;
	}
	const uv = tool["uv"];
	if (!isRecord(uv)) {
		/* v8 ignore next -- guarded by hasUvWorkspace before this function is called. */
		return null;
	}
	const workspace = uv["workspace"];
	return isRecord(workspace) ? workspace : null;
}

function expandMemberGlob(root: string, pattern: string): string[] {
	const parts = pattern.split("/");
	const results: string[] = [];
	walkGlob(root, parts, results);
	return results;
}

function walkGlob(directory: string, parts: string[], results: string[]): void {
	if (parts.length === 0) {
		if (isDirectory(directory)) {
			results.push(directory);
		}
		return;
	}
	const [part, ...rest] = parts;
	if (part === "*") {
		for (const entry of readDirSafe(directory)) {
			const child = `${directory}/${entry}`;
			if (isDirectory(child)) {
				walkGlob(child, rest, results);
			}
		}
		return;
	}
	walkGlob(`${directory}/${part}`, rest, results);
}

function isExcluded(relativePath: string, excludes: string[]): boolean {
	return excludes.some((pattern) =>
		globMatches(relativePath, pattern.replace(/\/$/, "")),
	);
}

function globMatches(value: string, pattern: string): boolean {
	if (pattern === value) {
		return true;
	}
	const regex = new RegExp(`^${pattern.split("*").map(escapeRegex).join(".*")}$`);
	return regex.test(value);
}

function findCurrentMember(cwd: string, members: string[]): string | null {
	const resolvedCwd = resolve(cwd);
	const matches = members.filter((member) => isRelativeTo(resolvedCwd, member));
	if (matches.length === 0) {
		return null;
	}
	return matches.sort((left, right) => right.length - left.length)[0] ?? null;
}

function ancestors(start: string): string[] {
	const result: string[] = [];
	let directory = resolve(start);
	while (true) {
		result.push(directory);
		const parent = resolve(directory, "..");
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

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFile(path: string): boolean {
	try {
		return statSync(path).isFile();
	} catch {
		/* v8 ignore next -- covers a race where a path disappears during stat. */
		return false;
	}
}

function isDirectory(path: string): boolean {
	try {
		return statSync(path).isDirectory();
	} catch {
		/* v8 ignore next -- covers a race where a path disappears during stat. */
		return false;
	}
}

function readDirSafe(path: string): string[] {
	try {
		return isDirectory(path) ? readdirSync(path) : [];
	} catch {
		/* v8 ignore next -- covers a race or permissions issue while reading. */
		return [];
	}
}

/* v8 ignore next 2 -- covered through glob matching behavior. */
const escapeRegex = (value: string): string =>
	value.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
