from pathlib import Path

import pytest

from library_skills.installer import (
    CLAUDE_SKILLS_DIR,
    UNIVERSAL_SKILLS_DIR,
    InstallError,
    get_target_dirs,
    install_skill,
    list_installed_skills,
    uninstall_skill,
)
from library_skills.scanner import Skill


def make_skill(tmp_path: Path, name: str = "demo-skill") -> Skill:
    skill_dir = tmp_path / "source" / ".agents" / "skills" / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {name}\ndescription: Demo skill.\n---\n",
        encoding="utf-8",
    )
    return Skill(
        name=name,
        description="Demo skill.",
        path=skill_md,
        package_name="demo-package",
        package_version="1.0.0",
        skill_dir=skill_dir,
    )


def test_get_target_dirs_always_includes_agents_and_optionally_claude(tmp_path):
    default_targets = get_target_dirs(tmp_path)
    assert len(default_targets) == 1
    assert default_targets[0].name == "universal"
    assert default_targets[0].path == tmp_path / UNIVERSAL_SKILLS_DIR

    targets = get_target_dirs(tmp_path, include_claude=True)

    assert [target.name for target in targets] == ["universal", "claude-compatible"]
    assert targets[0].path == tmp_path / UNIVERSAL_SKILLS_DIR
    assert targets[1].path == tmp_path / CLAUDE_SKILLS_DIR


def test_install_skill_creates_symlink_and_list_installed_skills_reports_it(tmp_path):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"

    installed_path = install_skill(skill, target_dir)

    assert installed_path.is_symlink()
    assert installed_path.resolve() == skill.skill_dir.resolve()

    installed = list_installed_skills(target_dir)
    assert len(installed) == 1
    assert installed[0].name == "demo-skill"
    assert installed[0].type == "symlink"
    assert installed[0].target == skill.skill_dir.resolve()
    assert installed[0].has_skill_md is True


def test_install_skill_copy_mode_copies_directory(tmp_path):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"

    installed_path = install_skill(skill, target_dir, copy=True)

    assert installed_path.is_dir()
    assert not installed_path.is_symlink()
    assert (installed_path / "SKILL.md").is_file()


def test_install_skill_refuses_to_overwrite_non_symlink_directory(tmp_path):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"
    (target_dir / skill.name).mkdir(parents=True)

    with pytest.raises(InstallError, match="Cannot overwrite non-symlink directory"):
        install_skill(skill, target_dir)


def test_uninstall_skill_only_removes_symlinks(tmp_path):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"
    installed_path = install_skill(skill, target_dir)
    hand_authored = target_dir / "hand-authored"
    hand_authored.mkdir()

    assert uninstall_skill(skill.name, target_dir) is True
    assert not installed_path.exists()
    assert uninstall_skill("hand-authored", target_dir) is False
    assert hand_authored.is_dir()
