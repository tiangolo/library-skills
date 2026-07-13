import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich_toolkit import RichToolkit
from rich_toolkit.menu import Menu, Option

from . import ui
from .deps import (
    get_node_workspace_top_level_deps,
    get_top_level_deps,
    get_workspace_top_level_deps,
)
from .installer import (
    FRAMEWORKS,
    TOOL_SKILL_MARKER,
    TOOL_SKILL_NAME,
    InstallError,
    InstallTarget,
    ToolSkillError,
    ToolSkillStatus,
    get_all_target_dirs,
    get_default_install_target_dirs,
    get_existing_target_dirs,
    get_target_dirs,
    inspect_tool_skill,
    install_skill,
    install_tool_skill,
    list_installed_skills,
    uninstall_skill,
)
from .python_env import (
    find_node_modules,
    find_project_root,
    find_venv,
    get_site_packages_dir,
)
from .scanner import (
    ScanResult,
    Skill,
    _normalize_package_name,
    scan_node_packages,
    scan_python_distributions,
)
from .workspace import (
    NodeWorkspace,
    UvWorkspace,
    find_node_workspace,
    find_uv_workspace,
    node_workspace_dependency_files,
    workspace_dependency_files,
)

console = ui.console

app = typer.Typer(
    name="library-skills",
    help="Discover and reconcile agent skills from installed library packages.",
    invoke_without_command=True,
)


@dataclass(frozen=True)
class ProjectContext:
    cwd: Path
    project_root: Path
    target_environment: Path | None
    site_packages_dir: Path | None
    node_modules_dir: Path | None
    workspace: UvWorkspace | None = None
    node_workspace: NodeWorkspace | None = None
    workspace_dependency_files: tuple[Path, ...] = ()
    node_workspace_dependency_files: tuple[Path, ...] = ()
    dependency_files: tuple[Path, ...] = ()


@dataclass(frozen=True)
class InstalledStatus:
    target: InstallTarget
    name: str
    type: str
    path: Path
    target_path: Path | None
    status: str
    skill: Skill | None = None


def _get_rich_toolkit() -> RichToolkit:
    return ui.get_toolkit(console=console)


def _get_project_context(cwd: Path | None = None) -> ProjectContext:
    cwd = cwd or Path.cwd()
    workspace = find_uv_workspace(cwd)
    node_workspace = find_node_workspace(cwd)
    project_root = (
        workspace.root
        if workspace is not None
        else node_workspace.root
        if node_workspace is not None
        else find_project_root(cwd) or cwd
    )
    workspace_files = (
        tuple(workspace_dependency_files(workspace)) if workspace is not None else ()
    )
    node_workspace_files = (
        tuple(node_workspace_dependency_files(node_workspace))
        if node_workspace is not None
        else ()
    )
    target_environment = find_venv(cwd)
    site_packages_dir = (
        get_site_packages_dir(target_environment) if target_environment else None
    )
    node_modules_dir = find_node_modules(cwd)
    return ProjectContext(
        cwd=cwd,
        project_root=project_root,
        target_environment=target_environment,
        site_packages_dir=site_packages_dir,
        node_modules_dir=node_modules_dir,
        workspace=workspace,
        node_workspace=node_workspace,
        workspace_dependency_files=workspace_files,
        node_workspace_dependency_files=node_workspace_files,
        dependency_files=workspace_files + node_workspace_files,
    )


def _scan_context(context: ProjectContext) -> ScanResult:
    result = ScanResult(environment_path=context.target_environment)
    if context.site_packages_dir is not None:
        python_result = scan_python_distributions(context.site_packages_dir)
        result.skills.extend(python_result.skills)
        result.warnings.extend(python_result.warnings)
    if context.workspace and context.workspace.current_member is not None:
        member_venv = context.workspace.current_member / ".venv"
        if member_venv.exists():
            result.warnings.append(
                f"Ignoring member-local .venv in uv workspace: {member_venv}"
            )
    if context.node_modules_dir is not None:
        node_result = scan_node_packages(context.node_modules_dir)
        result.skills.extend(node_result.skills)
        result.warnings.extend(node_result.warnings)
    if context.site_packages_dir is None and context.node_modules_dir is None:
        result.warnings.append(
            "No target Python environment with site-packages or node_modules was "
            "found. Run from a project root after installing dependencies, for "
            "example with 'uv sync' for Python or 'npm install' for Node.js."
        )
    result.environment_path = context.target_environment
    return result


def _print_warnings(warnings: list[str]) -> None:
    ui.print_warnings(warnings, console=console)


def _display_path(path: Path | None, project_root: Path) -> str:
    if path is None:
        return ""
    absolute_path = path if path.is_absolute() else Path.cwd() / path
    try:
        return str(absolute_path.relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _target_prompt_name(target: InstallTarget) -> str:
    if target.name == "universal":
        return "Agents (.agents/skills)"
    for fw in FRAMEWORKS.values():
        if target.name == fw.name:
            return fw.display_name
    return target.name


def _target_short_name(target: InstallTarget) -> str:
    if target.name == "universal":
        return "Agents"
    for fw in FRAMEWORKS.values():
        if target.name == fw.name:
            return fw.short_name
    return target.name


def _print_context(context: ProjectContext) -> None:
    rows = [("Project root", str(context.project_root))]
    if context.workspace is not None:
        rows.append(("Workspace root", str(context.workspace.root)))
        if context.workspace.current_member is not None:
            rows.append(("Workspace member", str(context.workspace.current_member)))
    elif context.node_workspace is not None:
        rows.append(("Workspace root", str(context.node_workspace.root)))
        if context.node_workspace.current_member is not None:
            rows.append(
                ("Workspace member", str(context.node_workspace.current_member))
            )
    if context.target_environment:
        rows.append(
            (
                "Target Python environment",
                _display_path(context.target_environment, context.project_root),
            )
        )
    else:
        rows.append(("Target Python environment", "not found"))
    if context.site_packages_dir:
        rows.append(
            (
                "Site-packages",
                _display_path(context.site_packages_dir, context.project_root),
            )
        )
    if context.node_modules_dir:
        rows.append(
            (
                "node_modules",
                _display_path(context.node_modules_dir, context.project_root),
            )
        )
    ui.print_title("context", console=console)
    ui.print_table(ui.context_table(rows), console=console)


def _print_skills_table(skills: list[Skill]) -> None:
    """Print a formatted table of discovered skills."""
    if not skills:
        ui.print_message("No skills found in installed packages.", console=console)
        return

    ui.print_table(
        ui.skills_table(
            [
                (
                    skill.name,
                    skill.package_name,
                    skill.package_version,
                    skill.description,
                )
                for skill in skills
            ]
        ),
        console=console,
    )


def _top_level_skills(
    *,
    context: ProjectContext,
    skills: list[Skill],
    include_all: bool,
) -> list[Skill]:
    """Filter discovered skills to top-level project dependencies by default."""
    if include_all:
        return skills

    top_level_deps = get_top_level_deps(context.project_root)
    if context.workspace is not None:
        top_level_deps = get_workspace_top_level_deps(
            list(context.workspace_dependency_files)
        )
        if context.node_workspace is not None:
            node_top_level_deps = get_node_workspace_top_level_deps(
                list(context.node_workspace_dependency_files)
            )
            if node_top_level_deps is not None:
                top_level_deps = (
                    node_top_level_deps
                    if top_level_deps is None
                    else top_level_deps | node_top_level_deps
                )
    elif context.node_workspace is not None:
        top_level_deps = get_node_workspace_top_level_deps(
            list(context.node_workspace_dependency_files)
        )
    if top_level_deps is None:
        return skills

    return [
        skill
        for skill in skills
        if _normalize_package_name(skill.package_name) in top_level_deps
    ]


def _scan_json_payload(
    *, context: ProjectContext, skills: list[Skill], result: ScanResult
) -> dict[str, object]:
    return {
        "project_root": str(context.project_root),
        "workspace_root": str(_workspace_root(context)),
        "workspace_member": (
            str(context.workspace.current_member)
            if context.workspace and context.workspace.current_member
            else str(context.node_workspace.current_member)
            if context.node_workspace and context.node_workspace.current_member
            else ""
        ),
        "dependency_files": [str(path) for path in context.dependency_files],
        "target_environment": str(context.target_environment or ""),
        "node_modules": str(context.node_modules_dir or ""),
        "skills": [
            {
                "name": skill.name,
                "description": skill.description,
                "package": skill.package_name,
                "version": skill.package_version,
                "path": str(skill.skill_dir),
            }
            for skill in skills
        ],
        "warnings": result.warnings,
    }


def _workspace_root(context: ProjectContext) -> Path | str:
    if context.workspace is not None:
        return context.workspace.root
    if context.node_workspace is not None:
        return context.node_workspace.root
    return ""


def _print_action_header(action: str) -> None:
    ui.print_action_header(action, console=console)


def _select_skills_interactive(skills: list[Skill]) -> list[Skill]:
    """Let the user interactively select which skills to install."""
    _print_action_header("install")
    return _get_rich_toolkit().ask(
        "Select skills to install (press Space to select, Enter to confirm):",
        options=[
            Option({"name": f"{skill.name} ({skill.package_name})", "value": skill})
            for skill in skills
        ],
        allow_filtering=True,
        multiple=True,
    )


def _select_targets_interactive(
    *, project_root: Path, default_targets: list[InstallTarget]
) -> list[InstallTarget]:
    """Let the user interactively select which targets to install into."""
    targets = get_all_target_dirs(project_root)
    default_names = {target.name for target in default_targets}
    toolkit = _get_rich_toolkit()
    menu = Menu(
        "Select installation targets (press Space to select, Enter to confirm):",
        options=[
            Option(
                {
                    "name": _target_prompt_name(target),
                    "value": target,
                }
            )
            for target in targets
        ],
        style=toolkit.style,
        console=toolkit.console,
        multiple=True,
    )
    menu.checked = {
        index for index, target in enumerate(targets) if target.name in default_names
    }
    return menu.ask()


def _select_install_targets(
    *,
    project_root: Path,
    enabled_frameworks: set[str],
    interactive: bool,
) -> list[InstallTarget]:
    if not interactive:
        return get_target_dirs(project_root, enabled_frameworks=enabled_frameworks)
    return _select_targets_interactive(
        project_root=project_root,
        default_targets=get_default_install_target_dirs(project_root),
    )


def _select_tool_skill_interactive() -> bool:
    toolkit = _get_rich_toolkit()
    menu = Menu(
        "Copy the Library Skills tool skill into the project so agents know how "
        "to update, repair, and check managed skills?",
        options=[
            Option(
                {
                    "name": "Copy Library Skills tool skill",
                    "value": True,
                }
            )
        ],
        style=toolkit.style,
        console=toolkit.console,
        multiple=True,
    )
    menu.checked = {0}
    return True in menu.ask()


def _find_collisions(skills: list[Skill]) -> set[str]:
    counts = Counter(skill.name for skill in skills)
    return {name for name, count in counts.items() if count > 1}


def _deduplicate_skills(skills: list[Skill]) -> list[Skill]:
    seen: set[Path] = set()
    unique: list[Skill] = []
    for skill in skills:
        key = skill.skill_dir.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(skill)
    return unique


def _filter_installable_skills(
    skills: list[Skill],
    *,
    selected_names: list[str],
    include_all: bool,
) -> list[Skill]:
    collisions = _find_collisions(skills)
    if collisions:
        ui.print_warning(
            "Skipping colliding skill names: " + ", ".join(sorted(collisions)),
            console=console,
        )

    installable = [skill for skill in skills if skill.name not in collisions]
    if selected_names:
        selected = set(selected_names)
        return [skill for skill in installable if skill.name in selected]
    if include_all:
        return installable
    return []


def _installed_statuses(
    *,
    targets: list[InstallTarget],
    skills: list[Skill],
) -> list[InstalledStatus]:
    skills_by_dir = {skill.skill_dir.resolve(): skill for skill in skills}
    skills_by_name = {skill.name: skill for skill in skills}
    statuses: list[InstalledStatus] = []

    for target in targets:
        for installed in list_installed_skills(target.path):
            if (
                installed.name == TOOL_SKILL_NAME
                and (installed.path / TOOL_SKILL_MARKER).exists()
            ):
                continue
            target_path = installed.target
            skill = skills_by_dir.get(target_path) if target_path else None

            status = "hand-authored"
            if installed.type == "symlink":
                if target_path is None or not target_path.exists():
                    status = "broken"
                    skill = skills_by_name.get(installed.name)
                elif skill:
                    status = (
                        "up to date"
                        if installed.name == skill.name
                        else "name mismatch"
                    )
                elif installed.name in skills_by_name:
                    skill = skills_by_name[installed.name]
                    status = "outdated"
                else:
                    status = "orphaned"

            statuses.append(
                InstalledStatus(
                    target=target,
                    name=installed.name,
                    type=installed.type,
                    path=installed.path,
                    target_path=target_path,
                    status=status,
                    skill=skill,
                )
            )

    installed_names = {
        (status.target.name, status.name)
        for status in statuses
        if status.status in {"up to date", "outdated", "broken", "name mismatch"}
    }
    for target in targets:
        for skill in skills:
            if (target.name, skill.name) not in installed_names:
                statuses.append(
                    InstalledStatus(
                        target=target,
                        name=skill.name,
                        type="missing",
                        path=target.path / skill.name,
                        target_path=skill.skill_dir,
                        status="new",
                        skill=skill,
                    )
                )
    return statuses


def _print_status_table(statuses: list[InstalledStatus], project_root: Path) -> None:
    ui.print_table(
        ui.status_table(
            [
                (
                    status.target.name,
                    status.name,
                    status.status,
                    _display_path(status.path, project_root),
                    _display_path(status.target_path, project_root),
                )
                for status in statuses
            ]
        ),
        console=console,
    )


def _print_tool_skill_status_table(
    statuses: list[ToolSkillStatus], project_root: Path
) -> None:
    ui.print_table(
        ui.tool_skill_status_table(
            [
                (
                    status.target.name,
                    status.status,
                    _display_path(status.path, project_root),
                )
                for status in statuses
            ]
        ),
        console=console,
    )


def _print_installed_skills_table(
    statuses: list[InstalledStatus], project_root: Path
) -> None:
    installed = [status for status in statuses if status.type != "missing"]
    if not installed:
        ui.print_message("No skills installed.", console=console)
        return
    _print_status_table(installed, project_root)


def _select_installed_skills_interactive(
    statuses: list[InstalledStatus],
) -> list[InstalledStatus]:
    """Let the user interactively select which installed skills to remove."""
    removable = [status for status in statuses if status.type == "symlink"]
    if not removable:
        return []
    return _get_rich_toolkit().ask(
        "Select skills to remove (press Space to select, Enter to confirm):",
        options=[
            Option(
                {
                    "name": f"{status.name} [{_target_short_name(status.target)}]",
                    "value": status,
                }
            )
            for status in removable
        ],
        allow_filtering=True,
        multiple=True,
    )


def _sync_target_dirs(
    *, project_root: Path, enabled_frameworks: set[str], yes: bool, check: bool
) -> list[InstallTarget]:
    targets_by_name = {
        target.name: target for target in get_existing_target_dirs(project_root)
    }
    default_targets = (
        get_target_dirs(project_root, enabled_frameworks=enabled_frameworks)
        if yes or check or enabled_frameworks
        else get_default_install_target_dirs(project_root)
    )
    for target in default_targets:
        targets_by_name[target.name] = target
    return list(targets_by_name.values())


def _repairable_statuses(statuses: list[InstalledStatus]) -> list[InstalledStatus]:
    return [
        status
        for status in statuses
        if status.type == "symlink"
        and status.status in {"broken", "outdated"}
        and status.skill is not None
    ]


def _removable_statuses(statuses: list[InstalledStatus]) -> list[InstalledStatus]:
    return [
        status
        for status in statuses
        if status.type == "symlink"
        and (
            status.status == "orphaned"
            or (status.status == "broken" and status.skill is None)
        )
    ]


def _select_statuses_interactive(
    statuses: list[InstalledStatus], *, action: str
) -> list[InstalledStatus]:
    if not statuses:
        return []
    _print_action_header(action)
    toolkit = _get_rich_toolkit()
    menu = Menu(
        f"Select skills to {action} (press Space to select, Enter to confirm):",
        options=[
            Option(
                {
                    "name": f"{status.name} [{_target_short_name(status.target)}]",
                    "value": status,
                }
            )
            for status in statuses
        ],
        style=toolkit.style,
        console=toolkit.console,
        multiple=True,
    )
    menu.checked = set(range(len(statuses)))
    return menu.ask()


def _repair_selected(*, statuses: list[InstalledStatus], project_root: Path) -> int:
    repaired_count = 0
    for status in statuses:
        if status.skill is None:
            continue
        install_skill(status.skill, status.target.path)
        ui.print_result(
            "Repaired",
            status.name,
            status.target.name,
            _display_path(status.path, project_root),
            console=console,
        )
        repaired_count += 1
    return repaired_count


def _remove_selected(*, statuses: list[InstalledStatus], project_root: Path) -> int:
    removed_count = 0
    for status in statuses:
        if uninstall_skill(status.name, status.target.path):
            ui.print_result(
                f"Removed {status.status} symlink",
                status.name,
                status.target.name,
                _display_path(status.path, project_root),
                console=console,
            )
            removed_count += 1
        else:
            ui.print_message(
                f"Not found: [bold]{status.name}[/bold] ({status.target.name})",
                console=console,
            )
    return removed_count


def _install_selected(
    *,
    skills: list[Skill],
    targets: list[InstallTarget],
    project_root: Path,
    copy: bool = False,
) -> int:
    installed_count = 0
    for target in targets:
        for skill in skills:
            try:
                dest = install_skill(skill, target.path, copy=copy)
            except InstallError as e:
                ui.print_skipped(skill.name, str(e), console=console)
                continue
            action = "Copied" if copy else "Installed"
            ui.print_result(
                action,
                skill.name,
                skill.package_name,
                _display_path(dest, project_root),
                console=console,
            )
            installed_count += 1
    if installed_count and not copy:
        ui.print_hint(
            "These relative symlinks can be committed to Git when your project "
            "uses stable repo-local installs. They resolve after dependencies "
            "are installed.",
            console=console,
        )
    return installed_count


def _sync_tool_skill(
    *,
    targets: list[InstallTarget],
    project_root: Path,
    check: bool,
    explicit: bool,
) -> tuple[int, bool]:
    statuses = [inspect_tool_skill(target.path) for target in targets]
    _print_tool_skill_status_table(statuses, project_root)

    drift = [status for status in statuses if status.status != "tool skill: up to date"]
    if check:
        return 0, bool(drift)

    changed_count = 0
    failed = False
    for status in drift:
        try:
            install_tool_skill(status.target.path)
        except ToolSkillError as e:
            ui.print_skipped("tool skill", str(e), console=console)
            failed = failed or explicit
            continue
        ui.print_result(
            "Copied",
            "library-skills",
            status.target.name,
            _display_path(status.path, project_root),
            console=console,
        )
        changed_count += 1
    return changed_count, failed


def _tool_skill_is_missing(targets: list[InstallTarget]) -> bool:
    return any(
        inspect_tool_skill(target.path).status == "tool skill: missing"
        for target in targets
    )


def _sync(
    *,
    enabled_frameworks: set[str],
    yes: bool,
    check: bool,
    include_all: bool,
    selected_names: list[str],
    copy: bool,
    tool_skill: bool | None,
) -> None:
    context = _get_project_context()
    result = _scan_context(context)
    targets = _sync_target_dirs(
        project_root=context.project_root,
        enabled_frameworks=enabled_frameworks,
        yes=yes,
        check=check,
    )

    _print_context(context)
    ui.print_line(console=console)
    _print_warnings(result.warnings)
    if result.warnings:
        ui.print_line(console=console)

    collisions = _find_collisions(result.skills)
    candidate_skills = _top_level_skills(
        context=context,
        skills=result.skills,
        include_all=include_all or bool(selected_names),
    )
    candidate_skill_names = {skill.name for skill in candidate_skills}
    statuses = _installed_statuses(
        targets=targets,
        skills=[skill for skill in result.skills if skill.name not in collisions],
    )
    visible_statuses = [
        status
        for status in statuses
        if status.status != "new" or status.name in candidate_skill_names
    ]

    if visible_statuses:
        ui.print_title("status", console=console)
        _print_status_table(visible_statuses, context.project_root)
    else:
        ui.print_message("No installed or discovered skills found.", console=console)

    drift = [
        status
        for status in statuses
        if status.status in {"broken", "outdated", "name mismatch", "orphaned"}
    ]
    if check:
        if tool_skill:
            ui.print_line(console=console)
            _, tool_failed = _sync_tool_skill(
                targets=get_target_dirs(
                    context.project_root, enabled_frameworks=enabled_frameworks
                ),
                project_root=context.project_root,
                check=True,
                explicit=True,
            )
            if tool_failed:
                raise typer.Exit(1)
        if drift or collisions:
            raise typer.Exit(1)
        return

    repairable = _repairable_statuses(drift)
    removable = _removable_statuses(drift)
    if drift:
        ui.print_title("attention", console=console)
        ui.print_warning("Some installed skills need attention.", console=console)
        ui.print_message(
            "Select the skills to install, repair, or remove.", console=console
        )
        ui.print_hint("Only managed symlinks will be changed.", console=console)

    selected_repairs = (
        repairable if yes else _select_statuses_interactive(repairable, action="repair")
    )
    selected_removals = (
        removable if yes else _select_statuses_interactive(removable, action="remove")
    )
    if selected_repairs:
        ui.print_line(console=console)
        _repair_selected(statuses=selected_repairs, project_root=context.project_root)
    if selected_removals:
        ui.print_line(console=console)
        _remove_selected(statuses=selected_removals, project_root=context.project_root)

    selected = _filter_installable_skills(
        candidate_skills,
        selected_names=selected_names,
        include_all=include_all,
    )
    if (
        not selected
        and not yes
        and not selected_names
        and not include_all
        and tool_skill is not True
    ):
        new_skills = [
            status.skill
            for status in visible_statuses
            if status.status == "new" and status.skill is not None
        ]
        if new_skills:
            selected = _select_skills_interactive(_deduplicate_skills(new_skills))

    tool_skill_changes = 0
    if selected:
        targets = _select_install_targets(
            project_root=context.project_root,
            enabled_frameworks=enabled_frameworks,
            interactive=not yes and not enabled_frameworks,
        )
        if not targets:
            ui.print_message("No installation targets selected.", console=console)
            return
        ui.print_line(console=console)
        installed_count = _install_selected(
            skills=selected,
            targets=targets,
            project_root=context.project_root,
            copy=copy,
        )
        ui.print_line(console=console)
        ui.print_summary({"installed skill targets": installed_count}, console=console)
    if tool_skill is True:
        ui.print_line(console=console)
        tool_skill_changes, tool_failed = _sync_tool_skill(
            targets=targets,
            project_root=context.project_root,
            check=False,
            explicit=True,
        )
        if tool_failed:
            raise typer.Exit(1)
    elif tool_skill is None and not yes and _tool_skill_is_missing(targets):
        if _select_tool_skill_interactive():
            ui.print_line(console=console)
            tool_skill_changes, _ = _sync_tool_skill(
                targets=targets,
                project_root=context.project_root,
                check=False,
                explicit=False,
            )
    if (
        not selected_repairs
        and not selected_removals
        and not selected
        and not tool_skill_changes
    ):
        ui.print_summary({}, console=console)


@app.callback()
def callback(
    ctx: typer.Context,
    include_claude: Annotated[
        bool,
        typer.Option(
            "--claude",
            help="Also install/manage skills in .claude/skills/ alongside .agents/skills/",
        ),
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompts")
    ] = False,
    check: Annotated[
        bool, typer.Option("--check", help="Validate only; exit 1 if installs drift")
    ] = False,
    include_all: Annotated[
        bool,
        typer.Option("--all", help="Install all newly discovered unmanaged skills"),
    ] = False,
    selected_names: Annotated[
        list[str] | None,
        typer.Option(
            "--skill", "-s", help="Install a specific discovered skill by name"
        ),
    ] = None,
    copy: Annotated[
        bool, typer.Option("--copy", help="Copy files instead of creating symlinks")
    ] = False,
    tool_skill: Annotated[
        bool | None,
        typer.Option(
            "--tool-skill/--no-tool-skill",
            help="Copy the Library Skills tool skill into the project",
        ),
    ] = None,
) -> None:
    """Discover and reconcile agent skills from installed library packages."""
    if ctx.invoked_subcommand is None:
        _sync(
            include_claude=include_claude,
            yes=yes,
            check=check,
            include_all=include_all,
            selected_names=selected_names or [],
            copy=copy,
            tool_skill=tool_skill,
        )


@app.command()
def scan(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    include_all: Annotated[
        bool,
        typer.Option("--all", help="Include skills from transitive dependencies"),
    ] = False,
) -> None:
    """Discover skills in installed packages."""
    context = _get_project_context()
    result = _scan_context(context)
    skills = _top_level_skills(
        context=context,
        skills=result.skills,
        include_all=include_all,
    )
    if json_output:
        payload = _scan_json_payload(context=context, skills=skills, result=result)
        print(json.dumps(payload, indent=2))
        return

    _print_context(context)
    ui.print_line(console=console)
    _print_warnings(result.warnings)
    if result.warnings:
        ui.print_line(console=console)
    _print_skills_table(skills)


@app.command("list")
def list_cmd(
    installed: Annotated[
        bool, typer.Option("--installed", help="Only show installed skills")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    include_claude: Annotated[
        bool,
        typer.Option(
            "--claude",
            help="Also include .claude/skills/ alongside .agents/skills/",
        ),
    ] = False,
    include_all: Annotated[
        bool,
        typer.Option("--all", help="Include skills from transitive dependencies"),
    ] = False,
) -> None:
    """List discovered or currently installed skills."""
    context = _get_project_context()
    result = _scan_context(context)
    skills = _top_level_skills(
        context=context,
        skills=result.skills,
        include_all=include_all,
    )
    targets = get_existing_target_dirs(
        context.project_root, include_claude=include_claude
    )
    statuses = _installed_statuses(targets=targets, skills=result.skills)

    if json_output:
        payload = _scan_json_payload(context=context, skills=skills, result=result)
        payload.update(
            {
                "installed": [
                    {
                        "target": status.target.name,
                        "name": status.name,
                        "status": status.status,
                        "path": str(status.path),
                        "source": str(status.target_path or ""),
                    }
                    for status in statuses
                    if status.type != "missing"
                ],
            }
        )
        print(json.dumps(payload, indent=2))
        return

    _print_warnings(result.warnings)
    if installed:
        _print_installed_skills_table(statuses, context.project_root)
    else:
        _print_skills_table(skills)


@app.command()
def install(
    include_claude: Annotated[
        bool,
        typer.Option(
            "--claude",
            help="Also install skills in .claude/skills/ alongside .agents/skills/",
        ),
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip interactive selection")
    ] = False,
    include_all: Annotated[
        bool,
        typer.Option("--all", help="Install all newly discovered unmanaged skills"),
    ] = False,
    selected_names: Annotated[
        list[str] | None,
        typer.Option(
            "--skill", "-s", help="Install a specific discovered skill by name"
        ),
    ] = None,
    copy: Annotated[
        bool, typer.Option("--copy", help="Copy files instead of creating symlinks")
    ] = False,
) -> None:
    """Install skills from installed packages."""
    context = _get_project_context()
    result = _scan_context(context)
    skills = _top_level_skills(
        context=context,
        skills=result.skills,
        include_all=include_all or bool(selected_names),
    )

    _print_warnings(result.warnings)
    selected = _filter_installable_skills(
        skills,
        selected_names=selected_names or [],
        include_all=include_all,
    )
    if not selected and not yes:
        selected = _select_skills_interactive(skills)

    if not selected:
        ui.print_message("No skills selected.", console=console)
        return

    targets = _select_install_targets(
        project_root=context.project_root,
        include_claude=include_claude,
        interactive=not yes and not include_claude,
    )
    if not targets:
        ui.print_message("No installation targets selected.", console=console)
        return

    installed_count = _install_selected(
        skills=selected, targets=targets, project_root=context.project_root, copy=copy
    )
    ui.print_line(console=console)
    ui.print_summary({"installed skill targets": installed_count}, console=console)


@app.command()
def remove(
    skill_names: Annotated[
        list[str] | None, typer.Argument(help="Names of skills to remove")
    ] = None,
    include_claude: Annotated[
        bool,
        typer.Option(
            "--claude",
            help="Also remove from .claude/skills/ alongside .agents/skills/",
        ),
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip interactive selection")
    ] = False,
) -> None:
    """Remove installed symlinked skills."""
    context = _get_project_context()
    result = _scan_context(context)
    targets = get_existing_target_dirs(
        context.project_root, include_claude=include_claude
    )
    statuses = _installed_statuses(targets=targets, skills=result.skills)

    selected_statuses: list[InstalledStatus] = []
    if skill_names:
        selected = set(skill_names)
        selected_statuses = [
            status
            for status in statuses
            if status.name in selected and status.type == "symlink"
        ]
    elif not yes:
        selected_statuses = _select_installed_skills_interactive(statuses)

    if not selected_statuses:
        ui.print_message("No skills selected.", console=console)
        return

    for status in selected_statuses:
        if uninstall_skill(status.name, status.target.path):
            ui.print_result(
                "Removed",
                status.name,
                status.target.name,
                _display_path(status.path, context.project_root),
                console=console,
            )
        else:
            ui.print_message(
                f"Not found: [bold]{status.name}[/bold] ({status.target.name})",
                console=console,
            )


def main() -> None:
    """CLI entry point."""
    app()
