# Reference

`library-skills` <abbr title="Command Line Interface">CLI</abbr> program reference.

---

Discover and install agent skills from installed library packages.

**Usage**:

```console
$ library-skills [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--claude`: Also install/manage skills in .claude/skills/ alongside .agents/skills/
* `-y, --yes`: Skip confirmation prompts
* `--check`: Validate only; exit 1 if installs drift
* `--all`: Install all newly discovered unmanaged skills
* `-s, --skill TEXT`: Install a specific discovered skill by name
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `scan`: Discover skills in installed packages.
* `list`: List discovered or currently installed...
* `install`: Install skills from installed packages.
* `remove`: Remove installed symlinked skills.

## `library-skills scan`

Discover skills in installed packages.

**Usage**:

```console
$ library-skills scan [OPTIONS]
```

**Options**:

* `--json`: Output as JSON
* `--all`: Include skills from transitive dependencies
* `--help`: Show this message and exit.

## `library-skills list`

List discovered or currently installed skills.

**Usage**:

```console
$ library-skills list [OPTIONS]
```

**Options**:

* `--installed`: Only show installed skills
* `--json`: Output as JSON
* `--claude`: Also include .claude/skills/ alongside .agents/skills/
* `--all`: Include skills from transitive dependencies
* `--help`: Show this message and exit.

## `library-skills install`

Install skills from installed packages.

**Usage**:

```console
$ library-skills install [OPTIONS]
```

**Options**:

* `--claude`: Also install skills in .claude/skills/ alongside .agents/skills/
* `-y, --yes`: Skip interactive selection
* `--all`: Install all newly discovered unmanaged skills
* `-s, --skill TEXT`: Install a specific discovered skill by name
* `--copy`: Copy files instead of creating symlinks
* `--help`: Show this message and exit.

## `library-skills remove`

Remove installed symlinked skills.

**Usage**:

```console
$ library-skills remove [OPTIONS] [SKILL_NAMES]...
```

**Arguments**:

* `[SKILL_NAMES]...`: Names of skills to remove

**Options**:

* `--claude`: Also remove from .claude/skills/ alongside .agents/skills/
* `-y, --yes`: Skip interactive selection
* `--help`: Show this message and exit.
