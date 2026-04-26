import csv
import json
import re
from dataclasses import dataclass, field
from email.parser import Parser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class Skill:
    """A discovered agent skill."""

    name: str
    description: str
    path: Path
    package_name: str
    skill_dir: Path
    package_version: str = ""


@dataclass
class ScanResult:
    """Result of scanning for skills."""

    skills: list[Skill] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    environment_path: Path | None = None


_SKILL_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def scan_python_distributions(site_packages: Path) -> ScanResult:
    """Scan target environment distribution metadata for bundled skills."""
    result = ScanResult()
    seen_skill_dirs: set[Path] = set()

    if not site_packages.is_dir():
        result.warnings.append(f"Site-packages directory not found: {site_packages}")
        return result

    for dist_info in sorted(site_packages.glob("*.dist-info")):
        if not dist_info.is_dir():
            continue

        dist = _read_distribution_info(dist_info)
        if dist is None:
            result.warnings.append(
                f"Skipping invalid distribution metadata: {dist_info}"
            )
            continue

        found = _scan_distribution_records(
            site_packages=site_packages,
            dist_info=dist_info,
            package_name=dist.name,
            package_version=dist.version,
            seen_skill_dirs=seen_skill_dirs,
        )
        result.skills.extend(found.skills)
        result.warnings.extend(found.warnings)

        if not found.skills:
            fallback = _scan_editable_direct_url(
                dist_info=dist_info,
                package_name=dist.name,
                package_version=dist.version,
                seen_skill_dirs=seen_skill_dirs,
            )
            result.skills.extend(fallback.skills)
            result.warnings.extend(fallback.warnings)

    return result


@dataclass(frozen=True)
class _DistributionInfo:
    name: str
    version: str


def _read_distribution_info(dist_info: Path) -> _DistributionInfo | None:
    metadata_path = dist_info / "METADATA"
    try:
        metadata_text = metadata_path.read_text(encoding="utf-8")
    except OSError:
        return None

    metadata = Parser().parsestr(metadata_text)
    name = metadata.get("Name")
    if not name:
        return None
    return _DistributionInfo(name=name, version=metadata.get("Version", ""))


def _scan_distribution_records(
    *,
    site_packages: Path,
    dist_info: Path,
    package_name: str,
    package_version: str,
    seen_skill_dirs: set[Path],
) -> ScanResult:
    result = ScanResult()
    record_path = dist_info / "RECORD"
    try:
        record_file = record_path.open(encoding="utf-8", newline="")
    except OSError:
        return result

    with record_file:
        for row in csv.reader(record_file):
            if not row:
                continue
            installed_path = row[0]
            if not _is_skill_file_record(installed_path):
                continue

            skill_md = (site_packages / installed_path).resolve()
            skill_dir = skill_md.parent
            if skill_dir in seen_skill_dirs:
                continue
            seen_skill_dirs.add(skill_dir)

            skill, warning = _load_skill(
                skill_dir=skill_dir,
                skill_md=skill_md,
                package_name=package_name,
                package_version=package_version,
            )
            if skill:
                result.skills.append(skill)
            elif warning:
                result.warnings.append(warning)

    return result


def _is_skill_file_record(installed_path: str) -> bool:
    parts = PurePosixPath(installed_path).parts
    for index, part in enumerate(parts):
        if part != ".agents":
            continue
        if (
            len(parts) > index + 3
            and parts[index + 1] == "skills"
            and parts[-1] == "SKILL.md"
        ):
            return True
    return False


def _scan_editable_direct_url(
    *,
    dist_info: Path,
    package_name: str,
    package_version: str,
    seen_skill_dirs: set[Path],
) -> ScanResult:
    result = ScanResult()

    source_root = _read_editable_source_root(dist_info)
    if source_root is None:
        return result

    for skill_md in sorted(source_root.rglob(".agents/skills/*/SKILL.md")):
        resolved_skill_md = skill_md.resolve()
        if not _is_relative_to(resolved_skill_md, source_root):
            continue

        skill_dir = resolved_skill_md.parent
        if skill_dir in seen_skill_dirs:
            continue
        seen_skill_dirs.add(skill_dir)

        skill, warning = _load_skill(
            skill_dir=skill_dir,
            skill_md=resolved_skill_md,
            package_name=package_name,
            package_version=package_version,
        )
        if skill:
            result.skills.append(skill)
        elif warning:
            result.warnings.append(warning)

    return result


def _read_editable_source_root(dist_info: Path) -> Path | None:
    direct_url_path = dist_info / "direct_url.json"
    try:
        data = json.loads(direct_url_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    dir_info = data.get("dir_info")
    if not isinstance(dir_info, dict) or dir_info.get("editable") is not True:
        return None

    url = data.get("url")
    if not isinstance(url, str):
        return None

    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None

    source_root = Path(unquote(parsed.path)).resolve()
    if source_root.is_dir():
        return source_root
    return None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _load_skill(
    *,
    skill_dir: Path,
    skill_md: Path,
    package_name: str,
    package_version: str,
) -> tuple[Skill | None, str | None]:
    metadata, warning = _parse_skill_frontmatter(skill_md)
    if warning:
        return None, f"{skill_md}: {warning}"

    name = metadata.get("name", "")
    description = metadata.get("description", "")
    validation_error = _validate_skill_metadata(
        name=name,
        description=description,
        parent_dir_name=skill_dir.name,
    )
    if validation_error:
        return None, f"{skill_md}: {validation_error}"

    return (
        Skill(
            name=name,
            description=description,
            path=skill_md,
            package_name=package_name,
            package_version=package_version,
            skill_dir=skill_dir,
        ),
        None,
    )


def _parse_skill_frontmatter(skill_md: Path) -> tuple[dict[str, str], str | None]:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return {}, f"could not read SKILL.md ({e})"

    if not text.startswith("---"):
        return {}, "missing YAML frontmatter"

    end = text.find("\n---", 3)
    if end == -1:
        return {}, "unterminated YAML frontmatter"

    frontmatter = text[3:end]
    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        key = key.strip()
        if key in {"name", "description"}:
            metadata[key] = value.strip().strip("\"'")

    return metadata, None


def _validate_skill_metadata(
    *,
    name: str,
    description: str,
    parent_dir_name: str,
) -> str | None:
    if not name:
        return "missing required 'name' field"
    if not _SKILL_NAME_RE.fullmatch(name) or "--" in name:
        return "invalid 'name' field; use lowercase letters, numbers, and hyphens only"
    if name != parent_dir_name:
        return f"'name' field must match parent directory name ({parent_dir_name})"
    if not description:
        return "missing required 'description' field"
    if len(description) > 1024:
        return "'description' field must be at most 1024 characters"
    return None


def _normalize_package_name(name: str) -> str:
    """Normalize a Python package name (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()
