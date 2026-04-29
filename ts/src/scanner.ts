import {
	existsSync,
	lstatSync,
	readFileSync,
	readdirSync,
	realpathSync,
} from "node:fs";
import {
	basename,
	dirname,
	isAbsolute,
	join,
	relative,
	resolve,
} from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "csv-parse/sync";

export interface Skill {
	name: string;
	description: string;
	path: string;
	packageName: string;
	skillDir: string;
	packageVersion: string;
}

export interface ScanResult {
	skills: Skill[];
	warnings: string[];
	environmentPath?: string;
}

interface DistributionInfo {
	name: string;
	version: string;
}

const SKILL_NAME_RE = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;

export function scanPythonDistributions(sitePackages: string): ScanResult {
	const result: ScanResult = { skills: [], warnings: [] };
	const seenSkillDirs = new Set<string>();

	if (!isDirectory(sitePackages)) {
		result.warnings.push(`Site-packages directory not found: ${sitePackages}`);
		return result;
	}

	for (const distInfo of readdirSync(sitePackages)
		.filter((entry) => entry.endsWith(".dist-info"))
		.sort()
		.map((entry) => join(sitePackages, entry))) {
		if (!isDirectory(distInfo)) {
			continue;
		}

		const dist = readDistributionInfo(distInfo);
		if (dist === null) {
			result.warnings.push(
				`Skipping invalid distribution metadata: ${distInfo}`,
			);
			continue;
		}

		const found = scanDistributionRecords({
			sitePackages,
			distInfo,
			packageName: dist.name,
			packageVersion: dist.version,
			seenSkillDirs,
		});
		result.skills.push(...found.skills);
		result.warnings.push(...found.warnings);

		if (found.skills.length === 0) {
			const fallback = scanEditableDirectUrl({
				distInfo,
				packageName: dist.name,
				packageVersion: dist.version,
				seenSkillDirs,
			});
			result.skills.push(...fallback.skills);
			result.warnings.push(...fallback.warnings);
		}
	}

	return result;
}

function readDistributionInfo(distInfo: string): DistributionInfo | null {
	let metadataText: string;
	try {
		metadataText = readFileSync(join(distInfo, "METADATA"), "utf8");
	} catch {
		return null;
	}

	const headers = parseMetadataHeaders(metadataText);
	const name = headers.get("name");
	if (!name) {
		return null;
	}

	return { name, version: headers.get("version") ?? "" };
}

function parseMetadataHeaders(text: string): Map<string, string> {
	const headers = new Map<string, string>();
	let currentKey: string | undefined;

	for (const line of text.split(/\r?\n/)) {
		if (line === "") {
			break;
		}
		if (/^\s/.test(line) && currentKey) {
			headers.set(
				currentKey,
				`${headers.get(currentKey) ?? ""} ${line.trim()}`,
			);
			continue;
		}
		const index = line.indexOf(":");
		if (index === -1) {
			continue;
		}
		currentKey = line.slice(0, index).trim().toLowerCase();
		headers.set(currentKey, line.slice(index + 1).trim());
	}

	return headers;
}

function scanDistributionRecords({
	sitePackages,
	distInfo,
	packageName,
	packageVersion,
	seenSkillDirs,
}: {
	sitePackages: string;
	distInfo: string;
	packageName: string;
	packageVersion: string;
	seenSkillDirs: Set<string>;
}): ScanResult {
	const result: ScanResult = { skills: [], warnings: [] };
	let recordText: string;
	try {
		recordText = readFileSync(join(distInfo, "RECORD"), "utf8");
	} catch {
		return result;
	}

	const rows = parse(recordText, {
		relaxColumnCount: true,
		skipEmptyLines: true,
	}) as string[][];

	for (const row of rows) {
		if (row.length === 0) {
			continue;
		}
		const installedPath = row[0];
		if (!isSkillFileRecord(installedPath)) {
			continue;
		}

		const skillMd = resolve(sitePackages, installedPath);
		const skillDir = dirname(skillMd);
		const resolvedSkillDir = realpathOrResolve(skillDir);
		if (seenSkillDirs.has(resolvedSkillDir)) {
			continue;
		}
		seenSkillDirs.add(resolvedSkillDir);

		const [skill, warning] = loadSkill({
			skillDir,
			skillMd,
			packageName,
			packageVersion,
		});
		if (skill) {
			result.skills.push(skill);
		} else if (warning) {
			result.warnings.push(warning);
		}
	}

	return result;
}

function isSkillFileRecord(installedPath: string): boolean {
	const parts = installedPath.split("/").filter((part) => part.length > 0);
	for (const [index, part] of parts.entries()) {
		if (part !== ".agents") {
			continue;
		}
		if (
			parts.length > index + 3 &&
			parts[index + 1] === "skills" &&
			parts.at(-1) === "SKILL.md"
		) {
			return true;
		}
	}
	return false;
}

function scanEditableDirectUrl({
	distInfo,
	packageName,
	packageVersion,
	seenSkillDirs,
}: {
	distInfo: string;
	packageName: string;
	packageVersion: string;
	seenSkillDirs: Set<string>;
}): ScanResult {
	const result: ScanResult = { skills: [], warnings: [] };
	const sourceRoot = readEditableSourceRoot(distInfo);
	if (sourceRoot === null) {
		return result;
	}

	for (const skillMd of findSkillMarkdownFiles(sourceRoot)) {
		const resolvedSkillMd = realpathOrResolve(skillMd);
		if (!isRelativeTo(resolvedSkillMd, sourceRoot)) {
			continue;
		}

		const skillDir = dirname(resolvedSkillMd);
		if (seenSkillDirs.has(skillDir)) {
			continue;
		}
		seenSkillDirs.add(skillDir);

		const [skill, warning] = loadSkill({
			skillDir,
			skillMd: resolvedSkillMd,
			packageName,
			packageVersion,
		});
		if (skill) {
			result.skills.push(skill);
		} else if (warning) {
			result.warnings.push(warning);
		}
	}

	return result;
}

function readEditableSourceRoot(distInfo: string): string | null {
	let data: unknown;
	try {
		data = JSON.parse(readFileSync(join(distInfo, "direct_url.json"), "utf8"));
	} catch {
		return null;
	}

	if (!isRecord(data)) {
		return null;
	}
	const dirInfo = data["dir_info"];
	if (!isRecord(dirInfo) || dirInfo["editable"] !== true) {
		return null;
	}
	const url = data["url"];
	if (typeof url !== "string") {
		return null;
	}

	let sourceRoot: string;
	try {
		sourceRoot = fileURLToPath(url);
	} catch {
		return null;
	}

	return isDirectory(sourceRoot) ? realpathOrResolve(sourceRoot) : null;
}

function findSkillMarkdownFiles(root: string): string[] {
	const found: string[] = [];

	function walk(directory: string): void {
		let entries: string[];
		try {
			entries = readdirSync(directory).sort();
		} catch {
			return;
		}
		for (const entry of entries) {
			const fullPath = join(directory, entry);
			let stat;
			try {
				stat = lstatSync(fullPath);
			} catch {
				continue;
			}
			if (stat.isSymbolicLink()) {
				if (entry === "SKILL.md" && isSkillMarkdownPath(root, fullPath)) {
					found.push(fullPath);
				}
				continue;
			}
			if (stat.isDirectory()) {
				walk(fullPath);
			} else if (entry === "SKILL.md" && isSkillMarkdownPath(root, fullPath)) {
				found.push(fullPath);
			}
		}
	}

	walk(root);
	return found;
}

function loadSkill({
	skillDir,
	skillMd,
	packageName,
	packageVersion,
}: {
	skillDir: string;
	skillMd: string;
	packageName: string;
	packageVersion: string;
}): [Skill | null, string | null] {
	const [metadata, warning] = parseSkillFrontmatter(skillMd);
	if (warning) {
		return [null, `${skillMd}: ${warning}`];
	}

	const name = metadata["name"] ?? "";
	const description = metadata["description"] ?? "";
	const validationError = validateSkillMetadata({
		name,
		description,
		parentDirName: basename(skillDir),
	});
	if (validationError) {
		return [null, `${skillMd}: ${validationError}`];
	}

	return [
		{
			name,
			description,
			path: skillMd,
			packageName,
			packageVersion,
			skillDir,
		},
		null,
	];
}

function parseSkillFrontmatter(
	skillMd: string,
): [Record<string, string>, string | null] {
	let text: string;
	try {
		text = readFileSync(skillMd, "utf8");
	} catch (error) {
		return [{}, `could not read SKILL.md (${String(error)})`];
	}

	if (!text.startsWith("---")) {
		return [{}, "missing YAML frontmatter"];
	}

	const end = text.indexOf("\n---", 3);
	if (end === -1) {
		return [{}, "unterminated YAML frontmatter"];
	}

	const metadata: Record<string, string> = {};
	for (const line of text.slice(3, end).split(/\r?\n/)) {
		const stripped = line.trim();
		if (stripped === "" || stripped.startsWith("#")) {
			continue;
		}
		const separator = stripped.indexOf(":");
		if (separator === -1) {
			continue;
		}
		const key = stripped.slice(0, separator).trim();
		if (key === "name" || key === "description") {
			metadata[key] = stripped
				.slice(separator + 1)
				.trim()
				.replace(/^["']|["']$/g, "");
		}
	}

	return [metadata, null];
}

function validateSkillMetadata({
	name,
	description,
	parentDirName,
}: {
	name: string;
	description: string;
	parentDirName: string;
}): string | null {
	if (!name) {
		return "missing required 'name' field";
	}
	if (!SKILL_NAME_RE.test(name) || name.includes("--")) {
		return "invalid 'name' field; use lowercase letters, numbers, and hyphens only";
	}
	if (name !== parentDirName) {
		return `'name' field must match parent directory name (${parentDirName})`;
	}
	if (!description) {
		return "missing required 'description' field";
	}
	if (description.length > 1024) {
		return "'description' field must be at most 1024 characters";
	}
	return null;
}

export function normalizePackageName(name: string): string {
	return name.replace(/[-_.]+/g, "-").toLowerCase();
}

function isDirectory(path: string): boolean {
	try {
		return lstatSync(path).isDirectory();
	} catch {
		return false;
	}
}

function isRelativeTo(path: string, parent: string): boolean {
	const childPath = resolve(path);
	const parentPath = resolve(parent);
	const childRelative = relative(parentPath, childPath);
	return (
		childRelative === "" ||
		(!childRelative.startsWith("..") && !isAbsolute(childRelative))
	);
}

function isSkillMarkdownPath(root: string, skillMd: string): boolean {
	const relativePath = relative(root, skillMd);
	if (relativePath === "" || relativePath.startsWith("..")) {
		return false;
	}
	const parts = relativePath.split(/[\\/]+/);
	return isSkillFileRecord(parts.join("/"));
}

function realpathOrResolve(path: string): string {
	try {
		return realpathSync(path);
	} catch {
		return resolve(path);
	}
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const testing = {
	isSkillFileRecord,
	readEditableSourceRoot,
	scanEditableDirectUrl,
};
