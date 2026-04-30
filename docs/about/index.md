# About Library Skills

## History

The idea started from a [post by Evan You](https://x.com/evanyou/status/2024595629134270918) (author of Vue.js, Vite, etc.).

Tanner Linsley (author of TanStack Query, TanStack Router, etc.) [commented with interest too](https://x.com/tannerlinsley/status/2024595851793092785).

I, Sebastián Ramírez (author of FastAPI, Typer, etc.) also [commented](https://x.com/tiangolo/status/2024905253854773474).

I proposed it as part of the [Agent Skills](https://github.com/agentskills/agentskills/pull/180) specification.

The specification maintainers suggested having the conversation in discussions first, noting that the change in the spec was the easy part, getting everyone onboard (adoption) was the difficult part.

I [commented with my proposal](https://github.com/agentskills/agentskills/issues/81#issuecomment-3941695652) there in the specification discussion repo.

I realized it could be easier to start with the adoption, by supporting it in [FastAPI](https://github.com/fastapi/fastapi/tree/master/fastapi/.agents/skills/fastapi), Typer, SQLModel, Asyncer, then [Streamlit added support](https://github.com/streamlit/streamlit/tree/develop/lib/streamlit/.agents/skills/developing-with-streamlit).

During this time, Tanner Linsley created TanStack Intent, with similar ideas, but scoped specifically to the npm ecosystem, and with some additional requirements / configurations, and added support for it to the [TanStack ecosystem](https://x.com/tannerlinsley/status/2030161512502022544).

Now I created this repo, website, and simple CLI tools to simplify installing and using library skills.

## Alternatives

There are other tools and ideas about sharing and distributing skills, but they refer to generic skills, not specific library skills, bundled and in sync with each version.
