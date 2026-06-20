import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from .scanner import _normalize_package_name

if sys.version_info >= (3, 11):  # pragma: no cover
    import tomllib
else:
    import tomli as tomllib


def get_python_top_level_deps(project_root: Path) -> set[str] | None:
    """Parse pyproject.toml to get top-level dependency names.

    Returns normalized package names, or None if no pyproject.toml found.
    """
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        return None

    return get_python_top_level_deps_from_files([pyproject])


def get_python_top_level_deps_from_files(pyprojects: list[Path]) -> set[str] | None:
    """Parse one or more pyproject.toml files to get top-level dependencies."""
    if not pyprojects:
        return None

    deps: set[str] = set()
    found = False
    for pyproject in pyprojects:
        if not pyproject.is_file():
            continue
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return None
        found = True
        _extract_python_top_level_deps(data, deps)
    return deps if found else None


def _extract_python_top_level_deps(data: dict[str, object], deps: set[str]) -> None:
    project = data.get("project", {})
    if isinstance(project, dict):
        project_data = cast("dict[str, object]", project)
        dependencies = project_data.get("dependencies", [])
        if isinstance(dependencies, list):
            _extract_deps_from_specs(dependencies, deps)

        optional_dependencies = project_data.get("optional-dependencies", {})
        if isinstance(optional_dependencies, dict):
            for group_dependencies in optional_dependencies.values():
                if isinstance(group_dependencies, list):
                    _extract_deps_from_specs(group_dependencies, deps)

    dependency_groups = data.get("dependency-groups", {})
    if isinstance(dependency_groups, dict):
        dependency_group_data = cast("dict[str, object]", dependency_groups)
        for group_name in dependency_group_data:
            _extract_deps_from_dependency_group(
                group_name,
                dependency_group_data,
                deps,
                visited=set(),
            )


def get_node_top_level_deps(project_root: Path) -> set[str] | None:
    """Parse package.json to get top-level dependency names."""
    package_json = project_root / "package.json"
    if not package_json.is_file():
        return None

    return get_node_top_level_deps_from_files([package_json])


def get_node_top_level_deps_from_files(
    package_json_files: list[Path],
) -> set[str] | None:
    """Parse one or more package.json files to get top-level dependencies."""
    if not package_json_files:
        return None

    deps: set[str] = set()
    found = False
    for package_json in package_json_files:
        if not package_json.is_file():
            continue
        data = _read_package_json(package_json)
        if data is None:
            return None
        found = True
        _extract_node_top_level_deps(data, deps)

    return deps if found else None


def _read_package_json(package_json: Path) -> dict[str, object] | None:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return {}

    return data


def _extract_node_top_level_deps(data: dict[str, object], deps: set[str]) -> None:
    for field in (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
    ):
        dependencies = data.get(field)
        if isinstance(dependencies, dict):
            for package_name in dependencies:
                if isinstance(package_name, str):
                    deps.add(_normalize_package_name(package_name))


def get_top_level_deps(project_root: Path) -> set[str] | None:
    """Parse project metadata to get top-level Python and Node dependency names."""
    dependency_sets = [
        deps
        for deps in (
            get_python_top_level_deps(project_root),
            get_node_top_level_deps(project_root),
        )
        if deps is not None
    ]
    if not dependency_sets:
        return None
    return set().union(*dependency_sets)


def get_workspace_top_level_deps(pyprojects: list[Path]) -> set[str] | None:
    """Parse Python dependency metadata for selected uv workspace files."""
    return get_python_top_level_deps_from_files(pyprojects)


def get_node_workspace_top_level_deps(
    package_json_files: list[Path],
) -> set[str] | None:
    """Parse Node dependency metadata for selected npm/Bun workspace files."""
    return get_node_top_level_deps_from_files(package_json_files)


def _extract_deps_from_specs(dep_specs: Sequence[object], deps: set[str]) -> None:
    """Extract package names from dependency spec strings."""
    for dep_spec in dep_specs:
        if not isinstance(dep_spec, str):
            continue
        pkg_name = re.split(r"[~>=<!\[;,\s]", dep_spec)[0].strip()
        if pkg_name and not pkg_name.startswith("#"):
            deps.add(_normalize_package_name(pkg_name))


def _extract_deps_from_dependency_group(
    group_name: str,
    dependency_groups: dict[str, object],
    deps: set[str],
    visited: set[str],
) -> None:
    """Extract package names from a PEP 735 dependency group."""
    if group_name in visited:
        return
    visited.add(group_name)

    group_dependencies = dependency_groups.get(group_name)
    if not isinstance(group_dependencies, list):
        return

    _extract_deps_from_specs(group_dependencies, deps)
    for group_dependency in group_dependencies:
        if not isinstance(group_dependency, dict):
            continue
        group_dependency_data = cast("dict[str, object]", group_dependency)
        include_group = group_dependency_data.get("include-group")
        if not isinstance(include_group, str):
            continue
        _extract_deps_from_dependency_group(
            include_group,
            dependency_groups,
            deps,
            visited,
        )
