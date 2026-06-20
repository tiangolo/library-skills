import fnmatch
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

if sys.version_info >= (3, 11):  # pragma: no cover
    import tomllib
else:
    import tomli as tomllib


@dataclass(frozen=True)
class UvWorkspace:
    root: Path
    members: tuple[Path, ...]
    current_member: Path | None


@dataclass(frozen=True)
class NodeWorkspace:
    root: Path
    members: tuple[Path, ...]
    current_member: Path | None


def find_uv_workspace(cwd: Path) -> UvWorkspace | None:
    """Find uv workspace metadata for cwd, if any."""
    for directory in [cwd, *cwd.parents]:
        pyproject = directory / "pyproject.toml"
        if not pyproject.is_file():
            continue
        data = _read_pyproject(pyproject)
        if not _has_uv_workspace(data):
            continue
        members = _find_workspace_members(directory, data)
        return UvWorkspace(
            root=directory,
            members=tuple(members),
            current_member=_find_current_member(cwd, members),
        )
    return None


def find_node_workspace(cwd: Path) -> NodeWorkspace | None:
    """Find npm/Bun package.json workspace metadata for cwd, if any."""
    for directory in [cwd, *cwd.parents]:
        package_json = directory / "package.json"
        if not package_json.is_file():
            continue
        data = _read_package_json(package_json)
        member_globs = _get_node_workspace_globs(data)
        if member_globs is None:
            continue
        members = _find_node_workspace_members(directory, member_globs)
        return NodeWorkspace(
            root=directory,
            members=tuple(members),
            current_member=_find_current_member(cwd, members),
        )
    return None


def workspace_dependency_files(workspace: UvWorkspace) -> list[Path]:
    """Return pyproject files used for default dependency filtering."""
    if workspace.current_member is not None:
        return [workspace.current_member / "pyproject.toml"]
    return [
        path
        for path in [workspace.root / "pyproject.toml"]
        + [member / "pyproject.toml" for member in workspace.members]
        if path.is_file()
    ]


def node_workspace_dependency_files(workspace: NodeWorkspace) -> list[Path]:
    """Return package.json files used for default dependency filtering."""
    if workspace.current_member is not None:
        return [workspace.current_member / "package.json"]
    return [
        path
        for path in [workspace.root / "package.json"]
        + [member / "package.json" for member in workspace.members]
        if path.is_file()
    ]


def _read_pyproject(path: Path) -> dict[str, object]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_package_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _has_uv_workspace(data: dict[str, object]) -> bool:
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return False
    tool_data = cast("dict[str, object]", tool)
    uv = tool_data.get("uv")
    if not isinstance(uv, dict):
        return False
    uv_data = cast("dict[str, object]", uv)
    return isinstance(uv_data.get("workspace"), dict)


def _find_workspace_members(root: Path, data: dict[str, object]) -> list[Path]:
    workspace = _get_workspace_table(data)
    if workspace is None:
        return []
    member_globs = workspace.get("members")
    if not isinstance(member_globs, list):
        return []
    exclude_globs = workspace.get("exclude")
    excludes = (
        [item for item in exclude_globs if isinstance(item, str)]
        if isinstance(exclude_globs, list)
        else []
    )

    members: set[Path] = set()
    for member_glob in member_globs:
        if not isinstance(member_glob, str):
            continue
        for member in root.glob(member_glob):
            if not member.is_dir():
                continue
            relative = member.relative_to(root).as_posix()
            if _is_excluded(relative, excludes):
                continue
            if (member / "pyproject.toml").is_file():
                members.add(member.resolve())
    return sorted(members)


def _get_node_workspace_globs(data: dict[str, object]) -> list[str] | None:
    workspaces = data.get("workspaces")
    if isinstance(workspaces, list):
        return [item for item in workspaces if isinstance(item, str)]
    if isinstance(workspaces, dict):
        workspace_data = cast("dict[str, object]", workspaces)
        packages = workspace_data.get("packages")
        if isinstance(packages, list):
            return [item for item in packages if isinstance(item, str)]
    return None


def _find_node_workspace_members(root: Path, member_globs: list[str]) -> list[Path]:
    includes = [pattern for pattern in member_globs if not pattern.startswith("!")]
    excludes = [pattern[1:] for pattern in member_globs if pattern.startswith("!")]

    members: set[Path] = set()
    for member_glob in includes:
        for member in root.glob(member_glob):
            if not member.is_dir():
                continue
            relative = member.relative_to(root).as_posix()
            if _is_excluded(relative, excludes):
                continue
            if (member / "package.json").is_file():
                members.add(member.resolve())
    return sorted(members)


def _get_workspace_table(data: dict[str, object]) -> dict[str, object] | None:
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    tool_data = cast("dict[str, object]", tool)
    uv = tool_data.get("uv")
    if not isinstance(uv, dict):
        return None
    uv_data = cast("dict[str, object]", uv)
    workspace = uv_data.get("workspace")
    return cast("dict[str, object]", workspace) if isinstance(workspace, dict) else None


def _is_excluded(relative_path: str, exclude_globs: list[str]) -> bool:
    return any(
        fnmatch.fnmatch(relative_path, pattern.rstrip("/"))
        or fnmatch.fnmatch(f"{relative_path}/", pattern)
        for pattern in exclude_globs
    )


def _find_current_member(cwd: Path, members: list[Path]) -> Path | None:
    cwd = cwd.resolve()
    matching_members = [
        member for member in members if _is_relative_to(cwd, member.resolve())
    ]
    if not matching_members:
        return None
    return max(matching_members, key=lambda path: len(path.parts))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
