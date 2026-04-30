<style>
.md-content .md-typeset h1 { display: none; }
</style>

<p align="center">
  <a href="https://library-skills.io"><img src="https://library-skills.io/img/logo-margin/logo-margin-vector.svg" alt="Library Skills"></a>
</p>
<p align="center">
    <em>Library Skills, AI Agents using libraries as intended, always up to date.</em>
</p>
<p align="center">
<a href="https://github.com/tiangolo/library-skills/actions?query=workflow%3ATest+event%3Apush+branch%3Amain">
    <img src="https://github.com/tiangolo/library-skills/actions/workflows/test.yml/badge.svg?event=push&branch=main" alt="Test">
</a>
<a href="https://github.com/tiangolo/library-skills/actions?query=workflow%3APublish">
    <img src="https://github.com/tiangolo/library-skills/actions/workflows/publish.yml/badge.svg" alt="Publish">
</a>
<a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/tiangolo/library-skills">
    <img src="https://coverage-badge.samuelcolvin.workers.dev/tiangolo/library-skills.svg" alt="Coverage">
<a href="https://pypi.org/project/library-skills">
    <img src="https://img.shields.io/pypi/v/library-skills?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
</p>

---

**Documentation**: [https://library-skills.io](https://library-skills.io)

**Source Code**: [https://github.com/tiangolo/library-skills](https://github.com/tiangolo/library-skills)

---

Let your AI agents use libraries as intended, **always up to date**.

Supporting libraries (e.g. [FastAPI](https://fastapi.tiangolo.com), [Streamlit](https://streamlit.io)) include their own AI skills ([https://agentskills.io](https://agentskills.io)) embedded, updated in sync with each new version of the library.

In Python, you can install them with:

```console
$ uvx library-skills
```

In JavaScript/TypeScript, you can install them with:

```console
$ npx library-skills
```

This will scan the dependencies for the current project, find the installed libraries, and ask you which of their skills you want to install in the project.

Then it will add them to the `.agents` directory as symbolic links, so when you update the libraries, the skills are updated too.

/// tip

If you are using Claude Code, add the `--claude` CLI Option to install the skills in the `.claude/skills` directory too, as Claude Code doesn't support the standard `.agents` directory.

///

## Why Library Skills

<abbr title="Large Language Models">LLMs</abbr> are great at helping you code, but are trained on data that existed until a certain point in time, which in the end, is always **old data**.

Additionally, they are trained on a lot of code examples, that in many cases use **old patterns**.

When there are **new features** or changes in the libraries, agents normally don't know about them, don't know how to use them, and insist on using old, deprecated, and sometimes hallucinated patterns.

But library authors can help them, providing **official library *skills*** that are always up to date, included in each new version of the package, in sync with the version of the library installed.

And you can install and use these official **Library Skills for Agents** with one command.

## License

This project is licensed under the terms of the [MIT license](https://github.com/tiangolo/library-skills/blob/main/LICENSE).
