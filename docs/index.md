#

<style>
.md-content .md-typeset h1 { display: none; }
</style>

<p align="center">
  <a href="https://library-skills.io"><img src="https://library-skills.io/img/logo-margin/logo-margin-vector.svg#only-light" alt="Library Skills"></a>
<!-- only-mkdocs -->
  <a href="https://library-skills.io"><img src="img/logo-margin/logo-margin-white-vector.svg#only-dark" alt="Library Skills"></a>
<!-- /only-mkdocs -->
</p>
<p align="center">
    <em>Library Skills, AI Agents using libraries, as intended, always up to date.</em>
</p>
<p align="center">
<a href="https://github.com/tiangolo/library-skills/actions?query=workflow%3ATest+event%3Apush+branch%3Amain">
    <img src="https://github.com/tiangolo/library-skills/actions/workflows/test.yml/badge.svg?event=push&branch=main" alt="Test">
</a>
<a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/tiangolo/library-skills">
    <img src="https://coverage-badge.samuelcolvin.workers.dev/tiangolo/library-skills.svg" alt="Coverage">
</a>
<a href="https://pypi.org/project/library-skills">
    <img src="https://img.shields.io/pypi/v/library-skills?color=%2334D058&label=pypi%20package" alt="Python package version">
</a>
<a href="https://www.npmjs.com/package/library-skills">
    <img src="https://img.shields.io/npm/v/library-skills?color=%2334D058&label=npm%20package" alt="npm package version">
</a>
</p>

---

**Documentation**: [https://library-skills.io](https://library-skills.io)

**Source Code**: [https://github.com/tiangolo/library-skills](https://github.com/tiangolo/library-skills)

---

Let your AI agents use libraries as intended, **always up to date**.

Supporting libraries (e.g. [FastAPI](https://fastapi.tiangolo.com), [Streamlit](https://streamlit.io)) include their own AI skills ([https://agentskills.io](https://agentskills.io)) embedded, updated in sync with each new version of the library.

In Python, you can install them with:

```bash
uvx library-skills
```

In JavaScript/TypeScript, you can install them with:

```bash
npx library-skills
```

This will scan the dependencies for the current project, find the installed libraries, and show the current skill installation status.

It can install new skills, repair managed symlinks that point to old skill locations, and remove managed symlinks for packages or skills that disappeared.

It will only remove managed symlinks, not hand-authored skill directories.

Then it will ask where to install new skills and add them as symbolic links, so when you update the libraries, the skills are updated too.

The symlinks are relative, so projects with stable repo-local installs can commit them to Git. They may be broken before dependencies are installed, then resolve after setup. On Windows, real symlink checkout can require Developer Mode or elevated permissions; use `--copy` if symlinks are not practical.

By default it selects `.agents/skills`, the agent-neutral target. If the project already has a `.claude/` directory, it selects `.claude/skills` too.

/// tip

If you are using Claude Code, select `.claude/skills` when asked for installation targets, as Claude Code doesn't support the standard `.agents` directory. For non-interactive installs, add the `--claude` CLI option to install the skills in `.claude/skills` too.

///

## Why Library Skills

<abbr title="Large Language Models">LLMs</abbr> are great at helping you code, but are trained on data that existed until a certain point in time, which in the end, is always **old data**.

Additionally, they are trained on a lot of code examples, that in many cases use **old patterns**.

When there are **new features** or changes in the libraries, agents normally don't know about them, don't know how to use them, and insist on using old, deprecated, and sometimes hallucinated patterns.

But library authors can help them, providing **official library *skills*** that are always up to date, included in each new version of the package, in sync with the version of the library installed.

And you can install and use these official **Library Skills for Agents** with one command.

## License

This project is licensed under the terms of the [MIT license](https://github.com/tiangolo/library-skills/blob/main/LICENSE).
