from pathlib import Path

SOURCE = Path("src/library_skills/tool_skill/SKILL.md")
TARGET = Path("ts/src/tool_skill/SKILL.md")


def main() -> None:
    TARGET.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
