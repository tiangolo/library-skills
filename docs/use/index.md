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
* Scan your project installation **environment**, e.g. `.venv` in Python or `node_modules` in Node.js.
* Find the **skills** available from the libraries you have installed, by default, filtered by your direct dependencies.
* Ask you which skills you want to **install**.
* For each skill you select, it will create a **symbolic link** in the `.agents` directory. If you are in a system that doesn't support symbolic links, you can make it copy the file with `--copy`.

/// tip

Only use `--copy` if your system doesn't support symbolic links (e.g. could happen on Windows).

By default, it will create symbolic links, which means that if you update the library, its skills will be automatically updated.

///

## Agents

This will work with AI Agents that support the `.agents` directory (most of them), including:

* Codex
* Cursor
* GitHub Copilot
* Pi
* Antigravity
* OpenCode

### Claude Code

If you are using Claude Code, it doesn't support the `.agents` directory, only the `.claude` directory. Then you can run the commands with `--claude` to use the `.claude` directory.

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

The CLI program `library-skills` is designed so you can easily run it with `uvx` or `npx`, without even having to install it.

That way, it will run in its own environment, but it still checks and scans *your project's environment* for the libraries you have installed.

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

The CLI is built in parallel in both Python and TypeScript, so you can use it for the ecosystem you prefer.

In both cases, the CLI will scan *both* the Python and Node.js environments, if any.

So, if you use Python, you can stay in Python, you don't even need Node.js installed to use it.

And if you use Node.js, you can stay in Node.js, you don't even need Python installed to use it.

And if you are in a project that has both Python and Node.js dependencies, it will find the skills from both ecosystems.
