const COLORS = {
	actionInstallBadge: "\u001b[1;37;42m",
	actionRemoveBadge: "\u001b[1;37;41m",
	actionRepairBadge: "\u001b[1;37;44m",
	attentionBadge: "\u001b[1;37;41m",
	contextBadge: "\u001b[1;37;46m",
	hintBadge: "\u001b[30;43m",
	resultBadge: "\u001b[1;37;42m",
	statusBadge: "\u001b[1;37;44m",
	warningBadge: "\u001b[1;37;43m",
	success: "\u001b[32m",
	warning: "\u001b[33m",
	error: "\u001b[31m",
	dim: "\u001b[2m",
	reset: "\u001b[0m",
} as const;

const STATUS_COLORS: Record<string, string> = {
	broken: COLORS.error,
	"hand-authored": COLORS.dim,
	"name mismatch": COLORS.warning,
	new: COLORS.success,
	orphaned: COLORS.error,
	outdated: COLORS.warning,
	"up to date": COLORS.dim,
};

export function printLine(): void {
	console.log();
}

export function printTitle(
	title: string,
	options: { before?: boolean } = {},
): void {
	if (options.before ?? true) {
		console.log();
	}
	console.log(badge(title, title));
}

export function printMessage(message: string): void {
	console.log(message);
}

export function printWarning(message: string): void {
	console.log(`${badge("warning", "Warning:")} ${message}`);
}

export function printHint(message: string): void {
	console.log(`${badge("hint", "Tip:")} ${message}`);
}

export function printActionHeader(
	action: "install" | "repair" | "remove",
	options: { before?: boolean } = {},
): void {
	const labels = {
		install: "Install new skills",
		repair: "Repair installed skills",
		remove: "Remove stale skills",
	};
	if (options.before ?? true) {
		console.log();
	}
	console.log(badge(`action.${action}`, labels[action]));
}

export function printResult({
	action,
	name,
	target,
	path,
}: {
	action: string;
	name: string;
	target: string;
	path: string;
}): void {
	console.log(`${badge("result", `${action}:`)} ${name} (${target}) -> ${path}`);
}

export function printSkipped(name: string, reason: string): void {
	console.log(`${badge("warning", "Skipped:")} ${name}: ${reason}`);
}

export function printSummary(items: Record<string, number>): void {
	const entries = Object.entries(items).filter(([, count]) => count > 0);
	if (entries.length === 0) {
		printMessage("No changes needed.");
		return;
	}
	if (entries.length === 1 && entries[0][0] === "installed skill targets") {
		printMessage(`Installed ${entries[0][1]} skill target(s).`);
		return;
	}
	console.log(
		`${badge("result", "Summary:")} ${entries
			.map(([name, count]) => `${name}: ${count}`)
			.join(", ")}`,
	);
}

export function printTable(
	columns: string[],
	rows: Array<Record<string, string>>,
): void {
	const widths = columns.map((column) =>
		Math.max(
			column.length,
			...rows.map((row) => stripAnsi(row[column] ?? "").length),
		),
	);
	const formatRow = (row: Record<string, string>) =>
		columns
			.map((column, index) => padAnsi(row[column] ?? "", widths[index]))
			.join("  ");

	console.log(formatRow(Object.fromEntries(columns.map((column) => [column, column]))));
	console.log(widths.map((width) => "-".repeat(width)).join("  "));
	for (const row of rows) {
		console.log(formatRow(row));
	}
}

export function styledStatus(status: string): string {
	const color = STATUS_COLORS[status];
	return color ? `${color}${status}${COLORS.reset}` : status;
}

function badge(kind: string, label: string): string {
	const badges: Record<string, string> = {
		"action.install": COLORS.actionInstallBadge,
		"action.remove": COLORS.actionRemoveBadge,
		"action.repair": COLORS.actionRepairBadge,
		attention: COLORS.attentionBadge,
		context: COLORS.contextBadge,
		hint: COLORS.hintBadge,
		result: COLORS.resultBadge,
		status: COLORS.statusBadge,
		warning: COLORS.warningBadge,
	};
	return `${badges[kind] ?? COLORS.dim} ${label} ${COLORS.reset}`;
}

function stripAnsi(value: string): string {
	return value.replace(/\u001b\[[0-9;]*m/g, "");
}

function padAnsi(value: string, width: number): string {
	return value + " ".repeat(Math.max(0, width - stripAnsi(value).length));
}
