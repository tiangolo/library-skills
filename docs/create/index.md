# Create Library Skills

Libraries can define their own skills in a `.agents/skills/` directory inside of their own package.

It is recommended to name them with a **prefix using their own name**, to avoid conflicts with other libraries.

For example, FastAPI could name a skill `fastapi/SKILL.md`, or `fastapi-development/SKILL.md`:

```
fastapi/.agents/skills/fastapi/SKILL.md
```

By bundling it with the published package, it will be available for agents when installed.

## In Python

For example, if the Python virtual environment being used is at `.venv`, the skill would end up located at:

```
.venv/lib/python3.14/site-packages/fastapi/.agents/skills/fastapi/SKILL.md
```

In this case using Python 3.14.

## In Node.js

A JavaScript library like `@tanstack/react-router` could include a skill at:

```
@tanstack/react-router/.agents/skills/tanstack-router/SKILL.md
```

When installed, the skill would end up located in a directory like:

```
node_modules/@tanstack/react-router/.agents/skills/tanstack-router/SKILL.md
```

## Agent Skills

Library Skills are the same standard [Agent Skills](https://agentskills.io/home), bundled with the library that provides them, and following the same format and conventions.

## Benefits

Libraries can provide their **official** skills instructing AI Agents how to work with them. They can define multiple skills if needed.

By using library skills, agents can make sure they follow the **best practices** defined by those libraries, **up to date** with their **latest versions**.
