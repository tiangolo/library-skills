import json
import os
import re
from pathlib import Path


def main() -> None:
    python_version = get_pyproject_version()
    typescript_version = get_package_json_version()
    release_version = os.environ["GITHUB_REF_NAME"]

    if python_version != typescript_version:
        raise SystemExit(
            "pyproject.toml version "
            f"({python_version}) does not match package.json version "
            f"({typescript_version})"
        )
    if python_version != release_version:
        raise SystemExit(
            f"Package version ({python_version}) does not match release tag "
            f"({os.environ['GITHUB_REF_NAME']})"
        )


def get_pyproject_version() -> str:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if match is None:
        raise SystemExit("Could not find pyproject.toml version")
    return match.group(1)


def get_package_json_version() -> str:
    data = json.loads(Path("package.json").read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str):
        raise SystemExit("Could not find package.json version")
    return version


if __name__ == "__main__":
    main()
