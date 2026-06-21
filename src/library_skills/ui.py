from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.theme import Theme
from rich_toolkit import RichToolkit
from rich_toolkit.styles import MinimalStyle

RICH_THEME = {
    "active": "green",
    "badge.action.install": "bold white on green",
    "badge.action.remove": "bold white on red",
    "badge.action.repair": "bold white on blue",
    "badge.attention": "bold white on red",
    "badge.context": "bold white on dark_cyan",
    "badge.hint": "black on yellow",
    "badge.result": "bold white on green",
    "badge.status": "bold white on blue",
    "badge.warning": "bold white on dark_orange",
    "cancelled": "red italic",
    "error": "red",
    "hint": "dim",
    "placeholder": "grey62",
    "placeholder.cancelled": "indian_red strike",
    "progress": "on green",
    "result": "white",
    "selected": "green",
    "status.broken": "red",
    "status.hand-authored": "dim",
    "status.name-mismatch": "yellow",
    "status.new": "green",
    "status.orphaned": "red",
    "status.outdated": "yellow",
    "status.up-to-date": "dim",
    "success": "green",
    "tag": "bold",
    "tag.title": "bold",
    "text": "white",
    "title.cancelled": "white",
    "title.error": "white",
    "warning": "yellow",
}

console = Console(theme=Theme(RICH_THEME))


def _console(override: Console | None = None) -> Console:
    return override or console


def get_toolkit(*, console: Console | None = None) -> RichToolkit:
    style = MinimalStyle(theme=RICH_THEME)
    style.console = _console(console)
    return RichToolkit(style=style)


def print_line(*, console: Console | None = None) -> None:
    _console(console).print()


def print_title(
    title: str,
    *,
    console: Console | None = None,
    before: bool = True,
) -> None:
    target_console = _console(console)
    if before:
        target_console.print()
    target_console.print(_badge(title, title))


def print_warning(message: str, *, console: Console | None = None) -> None:
    _console(console).print(f"{_badge('warning', 'Warning:')} {message}")


def print_hint(message: str, *, console: Console | None = None) -> None:
    _console(console).print(f"{_badge('hint', 'Tip:')} {message}")


def print_message(message: str, *, console: Console | None = None) -> None:
    _console(console).print(message)


def print_action_header(
    action: str, *, console: Console | None = None, before: bool = True
) -> None:
    labels = {
        "install": "Install new skills",
        "repair": "Repair installed skills",
        "remove": "Remove stale skills",
    }
    label = labels[action]
    target_console = _console(console)
    if before:
        target_console.print()
    target_console.print(f"{_badge(f'action.{action}', label)}")


def print_warnings(warnings: list[str], *, console: Console | None = None) -> None:
    for warning in warnings:
        print_warning(warning, console=console)


def context_table(rows: list[tuple[str, str]]) -> Table:
    table = Table.grid(padding=(0, 2), pad_edge=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for label, value in rows:
        table.add_row(label, value)
    return table


def skills_table(rows: list[tuple[str, str, str, str]]) -> Table:
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Skill", style="bold")
    table.add_column("Package")
    table.add_column("Version")
    table.add_column("Description")
    for row in rows:
        table.add_row(*row)
    return table


def status_table(rows: list[tuple[str, str, str, str, str]]) -> Table:
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Target")
    table.add_column("Skill", style="bold")
    table.add_column("Status")
    table.add_column("Path")
    table.add_column("Source")
    for target, skill, status, path, source in rows:
        table.add_row(target, skill, _styled_status(status), path, source)
    return table


def tool_skill_status_table(rows: list[tuple[str, str, str]]) -> Table:
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Target")
    table.add_column("Status")
    table.add_column("Path")
    for target, status, path in rows:
        table.add_row(target, _styled_status(status), path)
    return table


def print_table(table: Table, *, console: Console | None = None) -> None:
    _console(console).print(table)


def print_result(
    action: str,
    name: str,
    target: str,
    path: Path | str,
    *,
    console: Console | None = None,
) -> None:
    _console(console).print(
        f"{_badge('result', action + ':')} [bold]{name}[/bold] ({target}) -> {path}"
    )


def print_skipped(name: str, reason: str, *, console: Console | None = None) -> None:
    _console(console).print(
        f"{_badge('warning', 'Skipped:')} [bold]{name}[/bold]: {reason}"
    )


def _badge(kind: str, label: str) -> str:
    style = f"badge.{kind}"
    if style not in RICH_THEME:
        style = "tag"
    return f"[{style}] {label} [/]"


def _styled_status(status: str) -> str:
    style = {
        "broken": "status.broken",
        "hand-authored": "status.hand-authored",
        "name mismatch": "status.name-mismatch",
        "new": "status.new",
        "orphaned": "status.orphaned",
        "outdated": "status.outdated",
        "up to date": "status.up-to-date",
    }.get(status)
    if style is None:
        return status
    return f"[{style}]{status}[/]"


def print_summary(items: dict[str, int], *, console: Console | None = None) -> None:
    non_zero = {name: count for name, count in items.items() if count}
    if not non_zero:
        print_message("No changes needed.", console=console)
        return
    if set(non_zero) == {"installed skill targets"}:
        count = non_zero["installed skill targets"]
        print_message(f"Installed {count} skill target(s).", console=console)
        return
    summary = ", ".join(f"{name}: {count}" for name, count in non_zero.items())
    _console(console).print(f"{_badge('result', 'Summary:')} {summary}")
