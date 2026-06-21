from pathlib import Path

import pytest

import library_skills.installer as installer
from library_skills.installer import (
    CLAUDE_SKILLS_DIR,
    TOOL_SKILL_KIND,
    TOOL_SKILL_MARKER,
    TOOL_SKILL_NAME,
    UNIVERSAL_SKILLS_DIR,
    InstallError,
    ToolSkillError,
    _get_symlink_target,
    get_default_install_target_dirs,
    get_existing_target_dirs,
    get_target_dirs,
    get_tool_skill_template,
    get_tool_skill_version,
    inspect_tool_skill,
    install_skill,
    install_tool_skill,
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


def test_default_install_target_dirs_follow_project_state(tmp_path):
    assert [target.name for target in get_default_install_target_dirs(tmp_path)] == [
        "universal"
    ]

    agents_project = tmp_path / "agents-project"
    (agents_project / ".agents").mkdir(parents=True)
    assert [
        target.name for target in get_default_install_target_dirs(agents_project)
    ] == ["universal"]

    claude_project = tmp_path / "claude-project"
    (claude_project / ".claude").mkdir(parents=True)
    assert [
        target.name for target in get_default_install_target_dirs(claude_project)
    ] == ["claude-compatible"]

    both_project = tmp_path / "both-project"
    (both_project / ".agents").mkdir(parents=True)
    (both_project / ".claude").mkdir(parents=True)
    assert [
        target.name for target in get_default_install_target_dirs(both_project)
    ] == [
        "universal",
        "claude-compatible",
    ]


def test_existing_target_dirs_only_include_concrete_skills_dirs(tmp_path):
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".claude").mkdir()

    assert get_existing_target_dirs(tmp_path) == []

    (tmp_path / ".claude" / "skills").mkdir()

    assert [target.name for target in get_existing_target_dirs(tmp_path)] == [
        "claude-compatible"
    ]
    assert [
        target.name
        for target in get_existing_target_dirs(tmp_path, include_claude=True)
    ] == ["universal", "claude-compatible"]


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


def test_install_skill_symlink_failure_raises_install_error(tmp_path, monkeypatch):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"

    def fail_symlink(*args, **kwargs):
        raise OSError("symlink blocked")

    monkeypatch.setattr(Path, "symlink_to", fail_symlink)

    with pytest.raises(InstallError, match="Use --copy"):
        install_skill(skill, target_dir)


def test_install_skill_refuses_to_overwrite_non_symlink_directory(tmp_path):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"
    (target_dir / skill.name).mkdir(parents=True)

    with pytest.raises(InstallError, match="Cannot overwrite non-symlink directory"):
        install_skill(skill, target_dir)


def test_install_skill_refuses_to_overwrite_non_symlink_file(tmp_path):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"
    target_dir.mkdir(parents=True)
    (target_dir / skill.name).write_text("not managed", encoding="utf-8")

    with pytest.raises(InstallError, match="Cannot overwrite non-symlink file"):
        install_skill(skill, target_dir)


def test_install_skill_replaces_existing_symlink(tmp_path):
    skill = make_skill(tmp_path)
    target_dir = tmp_path / ".agents" / "skills"
    old_target = tmp_path / "old"
    old_target.mkdir()
    target_dir.mkdir(parents=True)
    dest = target_dir / skill.name
    dest.symlink_to(old_target, target_is_directory=True)

    install_skill(skill, target_dir)

    assert dest.is_symlink()
    assert dest.resolve() == skill.skill_dir.resolve()


def test_get_symlink_target_falls_back_to_absolute_on_relpath_error(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source"
    dest = tmp_path / "dest" / "demo-skill"
    source.mkdir()
    dest.parent.mkdir()

    def raise_value_error(_source: Path, *, start: Path) -> str:
        raise ValueError

    monkeypatch.setattr("library_skills.installer.os.path.relpath", raise_value_error)

    assert _get_symlink_target(source=source, dest=dest) == source


def test_get_symlink_target_uses_forward_slashes_for_relative_targets(
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "node_modules" / "pkg" / ".agents" / "skills" / "demo-skill"
    dest = tmp_path / ".agents" / "skills" / "demo-skill"

    monkeypatch.setattr(
        "library_skills.installer.os.path.relpath",
        lambda _source, *, start: r"..\..\node_modules\pkg\.agents\skills\demo-skill",
    )
    monkeypatch.setattr(installer.os, "sep", "\\")

    assert str(_get_symlink_target(source=source, dest=dest)) == (
        "../../node_modules/pkg/.agents/skills/demo-skill"
    )


def test_list_installed_skills_handles_missing_target_and_directories(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"

    assert list_installed_skills(target_dir) == []

    target_dir.mkdir(parents=True)
    (target_dir / "ignored.txt").write_text("ignored", encoding="utf-8")
    hand_authored = target_dir / "hand-authored"
    hand_authored.mkdir()

    installed = list_installed_skills(target_dir)

    assert len(installed) == 1
    assert installed[0].name == "hand-authored"
    assert installed[0].type == "directory"
    assert installed[0].target is None
    assert installed[0].has_skill_md is False


def test_list_installed_skills_reports_dangling_symlink(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"
    target_dir.mkdir(parents=True)
    dangling = target_dir / "dangling-skill"
    dangling.symlink_to(tmp_path / "missing-target", target_is_directory=True)

    installed = list_installed_skills(target_dir)

    assert len(installed) == 1
    assert installed[0].name == "dangling-skill"
    assert installed[0].type == "symlink"
    assert installed[0].target == (tmp_path / "missing-target").resolve()
    assert installed[0].has_skill_md is False


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


def test_uninstall_skill_removes_dangling_symlink(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"
    target_dir.mkdir(parents=True)
    dangling = target_dir / "dangling-skill"
    dangling.symlink_to(tmp_path / "missing-target", target_is_directory=True)

    assert uninstall_skill("dangling-skill", target_dir) is True
    assert not dangling.is_symlink()


def test_install_tool_skill_copies_template_and_marker(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"

    installed = install_tool_skill(target_dir)

    assert installed == target_dir / TOOL_SKILL_NAME
    assert installed.is_dir()
    assert (installed / "SKILL.md").read_text(encoding="utf-8") == (
        get_tool_skill_template()
    )
    marker = (installed / TOOL_SKILL_MARKER).read_text(encoding="utf-8")
    assert f'"kind": "{TOOL_SKILL_KIND}"' in marker
    assert inspect_tool_skill(target_dir).status == "tool skill: up to date"


def test_install_tool_skill_updates_managed_stale_copy(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"
    installed = install_tool_skill(target_dir)
    installed.joinpath("SKILL.md").write_text("stale", encoding="utf-8")

    assert inspect_tool_skill(target_dir).status == "tool skill: stale"

    install_tool_skill(target_dir)

    assert installed.joinpath("SKILL.md").read_text(encoding="utf-8") == (
        get_tool_skill_template()
    )


def test_tool_skill_version_falls_back_when_distribution_is_missing(monkeypatch):
    def missing_version(_distribution_name: str) -> str:
        raise installer.metadata.PackageNotFoundError

    monkeypatch.setattr(installer.metadata, "version", missing_version)

    assert get_tool_skill_version() == "0.0.0"


def test_inspect_tool_skill_reports_file_blocker(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"
    target_dir.mkdir(parents=True)
    (target_dir / TOOL_SKILL_NAME).write_text("not a directory", encoding="utf-8")

    status = inspect_tool_skill(target_dir)

    assert status.status == "tool skill: blocked by hand-authored directory"


def test_inspect_tool_skill_classifies_claude_target(tmp_path):
    target_dir = tmp_path / ".claude" / "skills"

    status = inspect_tool_skill(target_dir)

    assert status.target.name == "claude-compatible"


def test_inspect_tool_skill_reports_stale_when_managed_skill_md_is_missing(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"
    installed = target_dir / TOOL_SKILL_NAME
    installed.mkdir(parents=True)
    installed.joinpath(TOOL_SKILL_MARKER).write_text(
        '{"kind":"tool-skill"}', encoding="utf-8"
    )

    status = inspect_tool_skill(target_dir)

    assert status.status == "tool skill: stale"


def test_inspect_tool_skill_reports_stale_when_managed_skill_md_is_invalid_utf8(
    tmp_path,
):
    target_dir = tmp_path / ".agents" / "skills"
    installed = target_dir / TOOL_SKILL_NAME
    installed.mkdir(parents=True)
    installed.joinpath(TOOL_SKILL_MARKER).write_text(
        '{"kind":"tool-skill"}', encoding="utf-8"
    )
    installed.joinpath("SKILL.md").write_bytes(b"\xff")

    status = inspect_tool_skill(target_dir)

    assert status.status == "tool skill: stale"


def test_install_tool_skill_refuses_hand_authored_directory(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"
    hand_authored = target_dir / TOOL_SKILL_NAME
    hand_authored.mkdir(parents=True)
    hand_authored.joinpath("SKILL.md").write_text("mine", encoding="utf-8")

    status = inspect_tool_skill(target_dir)

    assert status.status == "tool skill: blocked by hand-authored directory"
    with pytest.raises(ToolSkillError, match="Cannot overwrite"):
        install_tool_skill(target_dir)
    assert hand_authored.joinpath("SKILL.md").read_text(encoding="utf-8") == "mine"


def test_install_tool_skill_refuses_invalid_marker(tmp_path):
    target_dir = tmp_path / ".agents" / "skills"
    installed = target_dir / TOOL_SKILL_NAME
    installed.mkdir(parents=True)
    installed.joinpath("SKILL.md").write_text("old", encoding="utf-8")
    installed.joinpath(TOOL_SKILL_MARKER).write_text(
        '{"kind":"other"}', encoding="utf-8"
    )

    status = inspect_tool_skill(target_dir)

    assert status.status == "tool skill: invalid marker"
    with pytest.raises(ToolSkillError, match="Cannot overwrite"):
        install_tool_skill(target_dir)
