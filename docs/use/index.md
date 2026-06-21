# Use Library Skills

In your project directory, run:

//// tab | Python uvx

```console
$ uvx library-skills
```

////

//// tab | Node.js npx

```console
$ npx library-skills
```

////

/// tip

That's all you need, if that worked, you can close this page, go build something. 😎

If you want to learn more, continue reading.

///

## How It Works

This command will:

* Check the **dependencies** you have defined, in `pyproject.toml` or `package.json`.
* Scan your project installation **environment**, e.g. a `.venv` directory or PEP 832 `.venv` redirect file in Python, or `node_modules` in Node.js.
* Find the **skills** available from the libraries you have installed, by default, filtered by your direct dependencies.
* Show the current skill installation status, including skills to install, repair, remove, or skip.
* Ask you which managed skill symlinks you want to **repair** or **remove**.
* Ask you which new skills you want to **install**.
* Ask which **installation targets** to use (`.agents/skills` or `.claude/skills`).
* For each skill and target you select, it will create a **symbolic link**. If you are in a system that doesn't support symbolic links, you can make it copy the file with `--copy`.

In uv workspaces, Library Skills uses the workspace environment and filters by the workspace member you run it from. In npm and Bun workspaces, it keeps normal `node_modules` discovery and applies the same workspace-aware dependency filtering. When you run it from the workspace root, it uses the root and all workspace members.

/// tip

Only use `--copy` if your system doesn't support symbolic links (e.g. could happen on Windows).

By default, it will create symbolic links, which means that if you update the library, its skills will be automatically updated.

///

## Committing Installed Skills

The installed skill symlinks are relative links. If your project uses stable, repo-local dependency installs, such as a project `.venv` or `node_modules`, you can commit those symlinks to Git so every user and agent sees the same selected skills.

The symlinks can be broken before dependencies are installed. That's expected: after users install the project dependencies, the links resolve to the skills included in those packages.

On Windows, committed symlinks work only when Git checks out real symlinks and Windows allows symlink creation, for example with Developer Mode enabled or elevated permissions. If symlinks are not practical in your environment, use `--copy` instead.

## Repairing Installed Skills

Run the default command again to reconcile installed skills with the libraries currently installed in your project:

//// tab | Python uvx

```console
$ uvx library-skills
```

////

//// tab | Node.js npx

```console
$ npx library-skills
```

////

Library Skills can repair managed symlinks when a skill moved to a new location, and it can remove managed symlinks when the package or skill disappeared.

It will not remove hand-authored skill directories or copied skill directories.

The status table can include:

* `new`: a discovered skill that is not installed yet.
* `up to date`: an installed symlink already pointing at the current skill.
* `broken`: a managed symlink whose target no longer exists.
* `outdated`: a managed symlink for a skill that still exists but points at an old location.
* `orphaned`: a managed symlink for a skill that is no longer discovered from installed packages.
* `name mismatch`: a symlink whose directory name does not match the skill it points to.
* `hand-authored`: a directory that is not managed as a symlink.

For non-interactive cleanup of managed symlink drift, use:

//// tab | Python uvx

```console
$ uvx library-skills --yes
```

////

//// tab | Node.js npx

```console
$ npx library-skills --yes
```

////

Use `--check` to validate the current state without changing files. It exits with status code 1 if installs drift.

## Pre-Commit Hook

You can run the same check in a pre-commit hook to catch skill drift when dependencies change.

Use [prek](https://github.com/j178/prek) to run pre-commit hooks:

```console
$ uvx prek install
```

Then add a local hook to `.pre-commit-config.yaml`:

//// tab | Python uvx

```yaml
repos:
  - repo: local
    hooks:
      - id: library-skills-check
        name: library-skills check
        entry: uvx library-skills --check
        language: system
        pass_filenames: false
        files: ^(pyproject\.toml|uv\.lock|package\.json|package-lock\.json)$
```

////

//// tab | Node.js npx

```yaml
repos:
  - repo: local
    hooks:
      - id: library-skills-check
        name: library-skills check
        entry: npx library-skills --check
        language: system
        pass_filenames: false
        files: ^(pyproject\.toml|uv\.lock|package\.json|package-lock\.json)$
```

////

If the hook fails, run `library-skills` to install, repair, or remove managed skills, then commit the resulting changes.

## Agents

This will work with AI Agents that support the `.agents` directory (most of them), including:

* Codex
* Cursor
* GitHub Copilot
* Pi
* Antigravity
* OpenCode

### Claude Code

If you are using Claude Code, it doesn't support the `.agents` directory, only the `.claude` directory.

When Library Skills asks for installation targets, select `.claude/skills`.

For non-interactive installs, use `--claude` to install in `.claude/skills` too.

//// tab | Python uvx

```console
$ uvx library-skills --claude
```

////

//// tab | Node.js npx

```console
$ npx library-skills --claude
```

////

## Other Installations

The <abbr title="Command Line Interface">CLI</abbr> program `library-skills` is designed to make it work with `uvx` or `npx`.

That way, it will run in its own temporary environment, but will still check and scan *your project's environment* for the libraries you have installed.

But in the end, it's just a Python or JavaScript CLI package that you can install and run in any other way.

For example, with pip:

```console
$ pip install library-skills
$ library-skills
```

Or with Bun:

```console
$ bunx library-skills
```

## Python and Node.js

The CLI is built in parallel in both Python and TypeScript, so you can use it from the ecosystem you prefer.

So, if you use Python, you can stay in Python, you don't even need Node.js installed.

And if you use Node.js, you can stay in Node.js, you don't even need Python installed.

In both cases, it will scan *both* the Python and Node.js environments, if available.

## JSON Output

For automation or scripts, use `scan --json` to get the discovered skills as machine-readable JSON:

//// tab | Python uvx

```console
$ uvx library-skills scan --json
```

////

//// tab | Node.js npx

```console
$ npx library-skills scan --json
```

////

The output includes the project root, detected workspace information (`workspace_root`, `workspace_member`, and `dependency_files`), detected Python environment, detected `node_modules` directory, discovered skills, and any warnings.

Use `list --json` to include the current installation status too:

//// tab | Python uvx

```console
$ uvx library-skills list --json
```

////

//// tab | Node.js npx

```console
$ npx library-skills list --json
```

////

The `list --json` output has the same fields as `scan --json`, plus an `installed` array with installed skill targets and status.
