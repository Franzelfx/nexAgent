# NexAgent — Copilot Instructions

These instructions apply to the entire NexAgent repository.

## Project Purpose

NexAgent is a compact LangGraph agent service built around a single ReAct-style graph, a small FastAPI wrapper, and Dokploy deployment via Traefik.

The codebase is intentionally small. Keep changes focused and avoid introducing framework-heavy abstractions unless there is a concrete need.

## Tech Stack

- Python 3.11
- LangGraph
- LangChain Core
- FastAPI
- Uvicorn
- Pydantic Settings
- Docker
- Dokploy with Traefik

## Architecture Rules

### FastAPI layer stays thin

Route handlers should only do the following:

- parse input
- call the graph
- shape the response
- expose health or redirect endpoints

Do not move graph logic or tool execution logic into API routes.

### Graph behavior belongs in graph/node files

- Graph topology belongs in `src/nexagent/graphs/`
- LLM node behavior belongs in `src/nexagent/agents/`
- State shape belongs in `src/nexagent/state/`

### Tools are the extension point

When adding capabilities, prefer adding or improving tools in `src/nexagent/tools/__init__.py` before expanding route logic.

Every new tool must:

- use `@tool`
- have a clear docstring
- accept typed inputs
- return simple serializable output
- be added to `ALL_TOOLS`

## Configuration Rules

- Environment-backed settings belong in `src/nexagent/config.py`
- New settings must have sensible defaults where possible
- Do not hardcode secrets, provider tokens, or deployment-specific values in source files
- Keep compatibility with both direct provider keys and LiteLLM proxy mode

## Deployment Rules

- Production routing is defined in `docker-compose-dokploy.yml`
- Public host is `agent.nexpatch.ai`
- `/studio` is a redirect endpoint to hosted LangGraph Studio, not a self-hosted static UI
- Preserve Dokploy compatibility: no `container_name`, use Traefik labels, keep external network `dokploy-network`

## Coding Style

- Prefer small, explicit functions over generic abstractions
- Keep imports straightforward and local style consistent with existing files
- Use type hints on public functions and models
- Avoid comments unless they clarify non-obvious behavior
- Preserve the repository's simple module layout

## API Expectations

Current public endpoints include:

- `/health`
- `/chat`
- `/docs`
- `/studio`

When changing response shapes or endpoint behavior, update README examples and keep backward compatibility unless the change is intentional.

## Testing Expectations

When changing graph, tools, or routes:

- update or add tests under `tests/`
- keep smoke tests passing
- prefer fast tests over broad integration harnesses unless specifically required

## Documentation Expectations

When behavior changes, update:

- `README.md` for developer and deployment usage
- examples for `/chat`, `/docs`, or `/studio` if affected
- environment variable docs if config changed

## Anti-Patterns To Avoid

- do not embed business logic in FastAPI route handlers
- do not add unused providers, SDKs, or frameworks
- do not introduce hidden magic around tool registration
- do not assume LangGraph Studio is self-hosted in this repo
- do not break Dokploy routing conventions