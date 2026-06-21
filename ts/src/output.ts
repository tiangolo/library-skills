const COLORS = {
	install: "\u001b[1;32m",
	repair: "\u001b[1;34m",
	remove: "\u001b[1;31m",
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

export function printTitle(title: string): void {
	console.log(title);
}

export function printMessage(message: string): void {
	console.log(message);
}

export function printWarning(message: string): void {
	console.log(`${COLORS.warning}Warning:${COLORS.reset} ${message}`);
}

export function printHint(message: string): void {
	console.log(`${COLORS.dim}Hint: ${message}${COLORS.reset}`);
}

export function printActionHeader(
	action: "install" | "repair" | "remove",
): void {
	const labels = {
		install: "Install new skills",
		repair: "Repair installed skills",
		remove: "Remove stale skills",
	};
	console.log(`${COLORS[action]}${labels[action]}${COLORS.reset}`);
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
	console.log(`${COLORS.success}${action}:${COLORS.reset} ${name} (${target}) -> ${path}`);
}

export function printSkipped(name: string, reason: string): void {
	console.log(`${COLORS.warning}Skipped:${COLORS.reset} ${name}: ${reason}`);
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
		`${COLORS.success}Summary: ${entries
			.map(([name, count]) => `${name}: ${count}`)
			.join(", ")}${COLORS.reset}`,
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

function stripAnsi(value: string): string {
	return value.replace(/\u001b\[[0-9;]*m/g, "");
}

function padAnsi(value: string, width: number): string {
	return value + " ".repeat(Math.max(0, width - stripAnsi(value).length));
}
