import json
import re
import sys
from pathlib import Path

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

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    deps: set[str] = set()
    project = data.get("project", {})
    if not isinstance(project, dict):
        return deps

    dependencies = project.get("dependencies", [])
    if isinstance(dependencies, list):
        _extract_deps_from_specs(dependencies, deps)

    optional_dependencies = project.get("optional-dependencies", {})
    if isinstance(optional_dependencies, dict):
        for group_dependencies in optional_dependencies.values():
            if isinstance(group_dependencies, list):
                _extract_deps_from_specs(group_dependencies, deps)

    return deps


def get_node_top_level_deps(project_root: Path) -> set[str] | None:
    """Parse package.json to get top-level dependency names."""
    package_json = project_root / "package.json"
    if not package_json.is_file():
        return None

    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return set()

    deps: set[str] = set()
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

    return deps


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


def _extract_deps_from_specs(dep_specs: list[object], deps: set[str]) -> None:
    """Extract package names from dependency spec strings."""
    for dep_spec in dep_specs:
        if not isinstance(dep_spec, str):
            continue
        pkg_name = re.split(r"[>=<!\[;,\s]", dep_spec)[0].strip()
        if pkg_name and not pkg_name.startswith("#"):
            deps.add(_normalize_package_name(pkg_name))
