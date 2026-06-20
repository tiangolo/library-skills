import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .scanner import Skill

UNIVERSAL_SKILLS_DIR = ".agents/skills"
CLAUDE_SKILLS_DIR = ".claude/skills"


@dataclass(frozen=True)
class InstallTarget:
    """A project-level skill installation target."""

    name: str
    path: Path


@dataclass(frozen=True)
class InstalledSkill:
    """A skill directory found in an installation target."""

    name: str
    type: str
    path: Path
    target: Path | None = None
    has_skill_md: bool = False


def get_target_dirs(
    project_root: Path, *, include_claude: bool = False
) -> list[InstallTarget]:
    """Get project-level target directories.

    The universal .agents/skills target is always included. Claude-compatible
    installs are additional and never replace the universal target.
    """
    targets = [
        InstallTarget(name="universal", path=project_root / UNIVERSAL_SKILLS_DIR)
    ]
    if include_claude:
        targets.append(
            InstallTarget(
                name="claude-compatible", path=project_root / CLAUDE_SKILLS_DIR
            )
        )
    return targets


def get_all_target_dirs(project_root: Path) -> list[InstallTarget]:
    """Get all supported project-level target directories."""
    return get_target_dirs(project_root, include_claude=True)


def get_default_install_target_dirs(project_root: Path) -> list[InstallTarget]:
    """Get interactive install target defaults from project state.

    Parent directories are enough to signal that the project uses a target. When
    neither target is present, prefer the universal .agents/skills target.
    """
    targets = get_all_target_dirs(project_root)
    by_name = {target.name: target for target in targets}
    selected: list[InstallTarget] = []

    if (project_root / ".agents").exists():
        selected.append(by_name["universal"])
    if (project_root / ".claude").exists():
        selected.append(by_name["claude-compatible"])

    if not selected:
        selected.append(by_name["universal"])
    return selected


def get_existing_target_dirs(
    project_root: Path, *, include_claude: bool = False
) -> list[InstallTarget]:
    """Get targets to inspect for existing installed skills.

    Without explicit Claude compatibility, this only returns concrete skills
    directories that already exist. With include_claude, preserve the legacy
    explicit behavior of managing both known targets.
    """
    if include_claude:
        return get_target_dirs(project_root, include_claude=True)
    return [
        target for target in get_all_target_dirs(project_root) if target.path.is_dir()
    ]


class InstallError(Exception):
    """Raised when a skill cannot be installed safely."""


def install_skill(
    skill: Skill,
    target_dir: Path,
    *,
    copy: bool = False,
) -> Path:
    """Install a single skill to the target directory.

    Returns the path to the installed skill directory.
    """
    dest = target_dir / skill.name
    source = skill.skill_dir.resolve()

    if dest.exists() or dest.is_symlink():
        if dest.is_symlink():
            dest.unlink()
        elif dest.is_file():
            raise InstallError(f"Cannot overwrite non-symlink file: {dest}")
        elif dest.is_dir():
            raise InstallError(f"Cannot overwrite non-symlink directory: {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)

    if copy:
        shutil.copytree(source, dest)
    else:
        link_target = _get_symlink_target(source=source, dest=dest)
        try:
            dest.symlink_to(link_target, target_is_directory=True)
        except OSError as e:
            raise InstallError(
                f"Could not create symlink: {e}. "
                "Use --copy if your system does not support symlinks."
            ) from e

    return dest


def _get_symlink_target(*, source: Path, dest: Path) -> Path:
    try:
        return Path(os.path.relpath(source, start=dest.parent.resolve()))
    except ValueError:
        return source


def uninstall_skill(skill_name: str, target_dir: Path) -> bool:
    """Remove an installed symlink. Returns True if something was removed."""
    dest = target_dir / skill_name
    if dest.is_symlink():
        dest.unlink()
        return True
    return False


def list_installed_skills(target_dir: Path) -> list[InstalledSkill]:
    """List skills currently installed in the target directory."""
    results: list[InstalledSkill] = []

    if not target_dir.is_dir():
        return results

    for child in sorted(target_dir.iterdir()):
        if not child.is_dir() and not child.is_symlink():
            continue
        skill_md = child / "SKILL.md"
        if child.is_symlink():
            install_type = "symlink"
            target = child.resolve()
        else:
            install_type = "directory"
            target = None

        results.append(
            InstalledSkill(
                name=child.name,
                type=install_type,
                path=child,
                target=target,
                has_skill_md=skill_md.is_file(),
            )
        )

    return results
