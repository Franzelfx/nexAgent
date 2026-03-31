# NexAgent

NexAgent is a LangGraph-based agent service with a FastAPI wrapper, tool-calling ReAct loop, Dokploy deployment, and a hosted LangGraph Studio entrypoint.

## What This Project Does

- Runs a single compiled LangGraph graph named `agent`
- Exposes a simple HTTP API for chat-style agent execution
- Supports direct provider keys or a LiteLLM proxy
- Logs tool calls in graph state for API responses
- Ships with Dokploy-ready Traefik routing on `agent.nexpatch.ai`
- Redirects `/studio` to hosted LangGraph Studio with the correct deployment URL

## Runtime Architecture

```
Client -> FastAPI -> LangGraph graph -> chat node -> tool node -> chat node -> END
```

Main flow:

1. `POST /chat` receives a user message.
2. The request is converted into `AgentState` with LangChain messages.
3. The `agent` node decides whether to answer directly or emit tool calls.
4. If tool calls exist, the `tools` node executes them.
5. Control returns to `agent` until no more tool calls are emitted.
6. The API returns the last model response plus `tool_calls_log`.

## Key Files

- [pyproject.toml](pyproject.toml): Python package metadata and dependencies
- [langgraph.json](langgraph.json): LangGraph graph registry
- [Dockerfile](Dockerfile): Production image build
- [docker-compose-dokploy.yml](docker-compose-dokploy.yml): Dokploy deployment definition
- [src/nexagent/api/__init__.py](src/nexagent/api/__init__.py): FastAPI app bootstrap
- [src/nexagent/api/routes.py](src/nexagent/api/routes.py): `/health`, `/chat`, `/studio`
- [src/nexagent/config.py](src/nexagent/config.py): Environment-backed settings
- [src/nexagent/graphs/__init__.py](src/nexagent/graphs/__init__.py): ReAct graph definition
- [src/nexagent/tools/__init__.py](src/nexagent/tools/__init__.py): Built-in tools and `ALL_TOOLS`
- [tests/test_graph.py](tests/test_graph.py): Smoke tests for graph compilation

## Project Structure

```
nexAgent/
├── .env.example
├── Dockerfile
├── README.md
├── docker-compose.dev.yml
├── docker-compose-dokploy.yml
├── langgraph.json
├── pyproject.toml
├── src/
│   └── nexagent/
│       ├── agents/
│       ├── api/
│       ├── graphs/
│       ├── state/
│       └── tools/
└── tests/
```

## Environment Variables

The service supports two LLM access modes.

### Direct provider keys

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEFAULT_MODEL`

### LiteLLM proxy

- `LITELLM_BASE_URL`
- `LITELLM_API_KEY`
- `DEFAULT_MODEL`

### Optional observability

- `LANGCHAIN_API_KEY`
- `LANGCHAIN_PROJECT`
- `LANGCHAIN_TRACING_V2`

## Local Development

### Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
PYTHONPATH=src uvicorn nexagent.api:app --host 0.0.0.0 --port 8123 --reload
```

### Docker Compose

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

## Public Endpoints

Production base URL:

- `https://agent.nexpatch.ai`

Main routes:

- `GET /health`
- `POST /chat`
- `GET /docs`
- `GET /studio`

Examples:

```bash
curl https://agent.nexpatch.ai/health

curl -X POST https://agent.nexpatch.ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it?"}'
```

## Studio Access

`/studio` does not serve a fully self-hosted UI bundle from this repository.

Instead, it redirects to hosted LangGraph Studio with this deployment URL prefilled as `baseUrl`:

- `https://agent.nexpatch.ai/studio`

If Studio blocks the domain, add the following to the allowed-domain list in Studio settings:

- `https://agent.nexpatch.ai`
- `agent.nexpatch.ai`

## Deploy with Dokploy

Dokploy expects a Compose deployment.

1. Create a Compose service.
2. Point it at `https://github.com/Franzelfx/nexAgent.git`.
3. Set Compose Path to `./docker-compose-dokploy.yml`.
4. Add required environment variables from `.env.example`.
5. Deploy.

Deployment behavior:

- Traefik routes `agent.nexpatch.ai` to the FastAPI container
- `/docs` exposes Swagger UI
- `/studio` redirects to hosted Studio
- Health check probes `http://127.0.0.1:8123/health`

## Development Conventions

### Tools

New tools belong in [src/nexagent/tools/__init__.py](src/nexagent/tools/__init__.py).

Rules:

- Use the `@tool` decorator
- Keep tool signatures simple and typed
- Return plain serializable values
- Register every new tool in `ALL_TOOLS`

Example:

```python
from langchain_core.tools import tool

@tool
def my_new_tool(query: str) -> str:
    return "result"

ALL_TOOLS = [get_current_time, calculator, my_new_tool]
```

### Graphs

The default graph lives in [src/nexagent/graphs/__init__.py](src/nexagent/graphs/__init__.py).

If you add another graph:

1. Create the graph module under `src/nexagent/graphs/`
2. Export a compiled graph object
3. Register it in [langgraph.json](langgraph.json)

### API

The FastAPI surface should stay thin:

- request parsing
- graph invocation
- response shaping
- redirects and health checks

Business logic belongs in graph nodes or tools, not in route handlers.

## Testing

Run tests with:

```bash
pytest
```

Current tests are lightweight smoke checks. Extend tests when changing:

- graph topology
- tool registration
- route behavior
- environment-dependent logic

## Observability

If `LANGCHAIN_TRACING_V2=true`, traces can be sent to LangSmith.

That is useful for:

- step-by-step graph inspection
- tool input/output debugging
- latency analysis
- prompt and model behavior review

## Current Limitations

- The public Studio experience depends on hosted Studio, not a self-hosted frontend bundle
- The built-in API is intentionally minimal and currently optimized for one graph
- Tooling is example-grade and should be extended carefully before broader production use
