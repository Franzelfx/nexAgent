# NexAgent

LangGraph-based AI agent platform with tool calling, sub-agents, and graph visualization.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   LangGraph Agent                    │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  Agent    │───▶│  Tools   │───▶│  Agent   │──▶…  │
│  │  (LLM)   │    │  (exec)  │    │  (LLM)   │      │
│  └──────────┘    └──────────┘    └──────────┘      │
│       │                                    │        │
│       ▼ no tool calls                      ▼        │
│     [END]                               [END]       │
└─────────────────────────────────────────────────────┘
```

The agent runs a **ReAct loop**: the LLM decides whether to call tools or return a final answer. Each iteration is a node in the LangGraph state graph. You can visualize this execution path using:

- **LangGraph Studio** (desktop app or CLI `langgraph dev`)
- **LangSmith** (cloud/self-hosted — set `LANGCHAIN_TRACING_V2=true`)

## Project Structure

```
nexAgent/
├── docker-compose-dokploy.yml   # Dokploy production deployment
├── docker-compose.dev.yml       # Local development
├── Dockerfile                   # Multi-stage build
├── langgraph.json               # LangGraph graph registry
├── pyproject.toml               # Python project config
├── .env.example                 # Environment variables template
├── src/
│   └── nexagent/
│       ├── config.py            # Settings from env vars
│       ├── agents/
│       │   └── chat.py          # LLM chat node
│       ├── api/
│       │   ├── __init__.py      # FastAPI app
│       │   └── routes.py        # API endpoints
│       ├── graphs/
│       │   ├── __init__.py      # Main agent graph definition
│       │   └── agent.py         # Graph export for langgraph.json
│       ├── state/
│       │   └── __init__.py      # AgentState (messages + tool log)
│       └── tools/
│           └── __init__.py      # Tool registry (calculator, time, …)
└── tests/
    └── test_graph.py            # Smoke tests
```

## Quick Start

### Local Development

```bash
# 1. Clone & enter
git clone https://github.com/Franzelfx/nexAgent.git
cd nexAgent

# 2. Create env
cp .env.example .env
# Edit .env — add at least one API key (OPENAI_API_KEY or LITELLM_*)

# 3a. Run with Docker
docker compose -f docker-compose.dev.yml up --build

# 3b. Or run directly with Python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=src uvicorn nexagent.api:app --host 0.0.0.0 --port 8123 --reload
```

### LangGraph Studio (Graph Visualization)

To see the agent execution as an interactive node/edge graph:

```bash
# Install LangGraph CLI
pip install langgraph-cli

# Run the studio dev server (opens browser UI)
PYTHONPATH=src langgraph dev
```

This starts a local server with a web UI that shows:
- The graph structure (nodes = agent, tools; edges = transitions)
- Live execution traces as the agent walks through the graph
- Tool call inputs/outputs at each step

### API Usage

```bash
# Chat with the agent
curl -X POST http://localhost:8123/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it?"}'

# Health check
curl http://localhost:8123/health
```

## Deploy with Dokploy

1. Create a **Compose** service in Dokploy
2. Point to this repo: `https://github.com/Franzelfx/nexAgent`
3. Set **Compose Path** to `./docker-compose-dokploy.yml`
4. Add environment variables in the Dokploy UI (see `.env.example`)
5. Deploy — Traefik labels handle HTTPS routing to `agent.nexpatch.ai`

## Adding Tools

Add new tools in `src/nexagent/tools/__init__.py`:

```python
from langchain_core.tools import tool

@tool
def my_new_tool(query: str) -> str:
    """Description shown to the LLM."""
    return "result"

# Register it
ALL_TOOLS = [get_current_time, calculator, my_new_tool]
```

The graph automatically picks up all tools from `ALL_TOOLS`.

## Adding Sub-Agents

Create a new graph in `src/nexagent/graphs/` and add it to `langgraph.json`:

```json
{
  "graphs": {
    "agent": "src.nexagent.graphs.agent:graph",
    "researcher": "src.nexagent.graphs.researcher:graph"
  }
}
```

## Observability

Set `LANGCHAIN_TRACING_V2=true` and provide a `LANGCHAIN_API_KEY` to send traces to [LangSmith](https://smith.langchain.com). This gives you:
- Full execution graph visualization
- Token usage per step
- Tool input/output inspection
- Latency breakdown per node
