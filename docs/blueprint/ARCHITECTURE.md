# NexAgent — Architecture Blueprint

> Agent Orchestration Platform Backend  
> Version: 0.2.0-draft | April 2026

---

## 1. Vision

NexAgent is a **lightweight but powerful agent orchestration backend**. Users configure a **3-layer tree** of agents and tools, then execute tasks through a master orchestrator that delegates to specialized sub-agents.

**Core principles:**
- Simple configuration, powerful execution
- Tree-structured orchestration: Master → Sub-Agents → Tools
- Full execution visibility via timeline/lane visualization
- Shared-database microservice citizen (FastAPI)
- No framework-heavy abstractions — explicit, small, readable code

---

## 2. Three-Layer Model

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: MASTER ORCHESTRATOR                       │
│  ─ One per workflow/project                         │
│  ─ Receives task instructions                       │
│  ─ Knows what each sub-agent can do (capability map)│
│  ─ Delegates, collects, synthesizes                 │
│  ─ Configured: model, system prompt, strategy       │
└──────────────┬──────────────────────────────────────┘
               │ delegates to
┌──────────────▼──────────────────────────────────────┐
│  Layer 2: SUB-AGENTS (employees)                    │
│  ─ Multiple per master                              │
│  ─ Each has: name, role description, model, API key │
│  ─ Each has: a set of bound tools                   │
│  ─ Acts autonomously within delegated scope         │
│  ─ Returns structured results to master             │
└──────────────┬──────────────────────────────────────┘
               │ uses
┌──────────────▼──────────────────────────────────────┐
│  Layer 3: TOOLS                                     │
│  ─ Reusable across sub-agents                       │
│  ─ Registered with name, description, input schema  │
│  ─ Built-in tools + user-defined (API, code, etc.)  │
│  ─ Each tool is a callable unit with typed I/O      │
└─────────────────────────────────────────────────────┘
```

---

## 3. Configuration Phase vs. Execution Phase

### 3.1 Configuration Phase (Design Time)

Users build an **agent tree** through the UI (drag-and-drop node builder):

1. **Register tools** — define or import tools with name, description, input/output schema
2. **Create sub-agents** — name, role description, model provider, model name, API key, system prompt, attach tools
3. **Create master orchestrator** — model config, orchestration strategy, attach sub-agents, define the capability map (auto-derived from sub-agent descriptions + tool descriptions)

The configuration is persisted as a **workflow definition** in the database.

### 3.2 Execution Phase (Run Time)

1. User sends a **task** (instruction text) to a configured master orchestrator
2. Master receives task + its **capability map** (what each sub-agent can do)
3. Master plans delegation: which sub-agents to invoke, in what order, with what sub-tasks
4. Sub-agents execute (potentially in parallel lanes), using their bound tools
5. Results flow back to the master for synthesis
6. Full execution trace is recorded for the timeline visualization

---

## 4. System Architecture

```
                    ┌──────────────┐
                    │   Frontend   │
                    │  (future)    │
                    │  Node Builder│
                    │  + Timeline  │
                    └──────┬───────┘
                           │ REST / WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    NexAgent FastAPI Service                   │
│                                                              │
│  ┌─────────────────────────────┐  ┌────────────────────────┐ │
│  │  Configuration API          │  │  Execution API         │ │
│  │  POST /workflows            │  │  POST /execute         │ │
│  │  CRUD /tools                │  │  GET  /executions/{id} │ │
│  │  CRUD /sub-agents           │  │  WS   /executions/live │ │
│  │  CRUD /orchestrators        │  │                        │ │
│  └─────────────┬───────────────┘  └────────────┬───────────┘ │
│                │                                │             │
│  ┌─────────────▼────────────────────────────────▼───────────┐ │
│  │              Orchestration Engine                         │ │
│  │                                                           │ │
│  │  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐  │ │
│  │  │ Workflow Loader│  │ Master Runner│  │ Lane Manager  │  │ │
│  │  │ (DB → Graph)  │  │ (LangGraph)  │  │ (parallel     │  │ │
│  │  │               │  │              │  │  sub-agent     │  │ │
│  │  │               │  │              │  │  execution)    │  │ │
│  │  └───────────────┘  └──────────────┘  └───────────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                          │                                     │
│  ┌───────────────────────▼─────────────────────────────────┐   │
│  │              Tool Registry & Executor                    │   │
│  │  Built-in tools + dynamically loaded user tools          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │  Shared PostgreSQL   │
                │  (microservice DB)   │
                │                      │
                │  nexagent schema:    │
                │  ─ workflows         │
                │  ─ tool_definitions  │
                │  ─ sub_agents        │
                │  ─ orchestrators     │
                │  ─ executions        │
                │  ─ execution_steps   │
                └─────────────────────┘
```

---

## 5. Execution Model — "Guitar" Timeline

The "guitar visualization" maps to **lanes on a timeline**:

```
Time ──────────────────────────────────────────────────►

Lane 0 (Master)  ═══▶ [Plan] ═══════════▶ [Collect] ══▶ [Synthesize] ══▶ [Done]
                          │                    ▲
                          ├──── delegate ──────┤
                          │                    │
Lane 1 (Agent A)      [Task A1] ──▶ [Tool X] ─┤
                                               │
Lane 2 (Agent B)      [Task B1] ──▶ [Tool Y] ──▶ [Tool Z] ─┘
                                               │
Lane 3 (Agent C)              [Task C1] ──────┘
```

**Key concepts:**

| Concept | Description |
|---|---|
| **Lane** | One horizontal track per actor (master + each active sub-agent) |
| **Step** | A discrete execution unit within a lane (LLM call, tool call, delegation) |
| **Checkpoint** | Master picks up results from completed lanes and continues |
| **Execution** | The full run from task input to final output, across all lanes |

Each step records: `lane_id`, `step_index`, `type` (llm_call | tool_call | delegation | synthesis), `input`, `output`, `started_at`, `finished_at`, `tokens_used`, `status`.

---

## 6. API Design (Planned Endpoints)

### Configuration Endpoints

```
POST   /api/v1/tools                    Create a tool definition
GET    /api/v1/tools                    List tools
GET    /api/v1/tools/{id}               Get tool
PUT    /api/v1/tools/{id}               Update tool
DELETE /api/v1/tools/{id}               Delete tool

POST   /api/v1/sub-agents               Create a sub-agent
GET    /api/v1/sub-agents               List sub-agents
GET    /api/v1/sub-agents/{id}          Get sub-agent
PUT    /api/v1/sub-agents/{id}          Update sub-agent (model, tools, etc.)
DELETE /api/v1/sub-agents/{id}          Delete sub-agent

POST   /api/v1/orchestrators            Create a master orchestrator
GET    /api/v1/orchestrators            List orchestrators
GET    /api/v1/orchestrators/{id}       Get orchestrator (includes capability map)
PUT    /api/v1/orchestrators/{id}       Update orchestrator
DELETE /api/v1/orchestrators/{id}       Delete orchestrator

POST   /api/v1/workflows                Create a full workflow (orchestrator + agents + tools wiring)
GET    /api/v1/workflows/{id}           Get workflow definition
GET    /api/v1/workflows/{id}/graph     Get the node-graph representation for UI
```

### Execution Endpoints

```
POST   /api/v1/execute                   Start a task execution
GET    /api/v1/executions                List executions
GET    /api/v1/executions/{id}           Get execution with all steps
GET    /api/v1/executions/{id}/timeline  Get lane-based timeline view
WS     /api/v1/executions/{id}/live      WebSocket stream of live execution steps
POST   /api/v1/executions/{id}/cancel    Cancel running execution
```

### Existing Endpoints (Preserved)

```
GET    /health                           Health check
POST   /chat                             Simple single-agent chat (backward compat)
GET    /studio                           Redirect to LangGraph Studio
GET    /docs                             OpenAPI docs
```

---

## 7. Module Layout (Target)

```
src/nexagent/
├── __init__.py
├── config.py                       # Settings (env-based)
├── database.py                     # SQLAlchemy async engine + session (shared DB)
│
├── models/                         # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── base.py                     # Declarative base, schema config
│   ├── tool_definition.py
│   ├── sub_agent.py
│   ├── orchestrator.py
│   ├── workflow.py
│   ├── execution.py
│   └── execution_step.py
│
├── schemas/                        # Pydantic request/response schemas
│   ├── __init__.py
│   ├── tools.py
│   ├── sub_agents.py
│   ├── orchestrators.py
│   ├── workflows.py
│   └── executions.py
│
├── api/                            # FastAPI routes (thin layer)
│   ├── __init__.py                 # App factory, middleware
│   ├── routes.py                   # Legacy /chat, /health, /studio
│   ├── tools_router.py
│   ├── sub_agents_router.py
│   ├── orchestrators_router.py
│   ├── workflows_router.py
│   └── executions_router.py
│
├── services/                       # Business logic (called by routes)
│   ├── __init__.py
│   ├── tool_service.py             # CRUD + validation for tools
│   ├── sub_agent_service.py        # CRUD + model validation
│   ├── orchestrator_service.py     # CRUD + capability map builder
│   ├── workflow_service.py         # Workflow assembly + graph export
│   └── execution_service.py        # Run orchestration, track lanes
│
├── engine/                         # Orchestration runtime
│   ├── __init__.py
│   ├── master_runner.py            # Master orchestrator LangGraph loop
│   ├── sub_agent_runner.py         # Sub-agent execution (isolated ReAct loop)
│   ├── lane_manager.py             # Manages parallel lanes, results collection
│   ├── capability_map.py           # Builds capability descriptions for master
│   └── tool_executor.py            # Resolves + executes tools from definitions
│
├── agents/                         # LLM node implementations
│   ├── __init__.py
│   └── chat.py                     # Existing single-agent chat node
│
├── graphs/                         # LangGraph graph definitions
│   ├── __init__.py                 # Existing simple ReAct graph
│   └── agent.py                    # LangGraph alias
│
├── state/                          # State shapes
│   ├── __init__.py                 # Existing AgentState
│   └── orchestration.py            # OrchestrationState (multi-lane)
│
└── tools/                          # Built-in tool implementations
    └── __init__.py                 # Existing tools + ALL_TOOLS registry
```

---

## 8. Capability Map

The master orchestrator needs to know what each sub-agent can do. This is auto-generated from configuration:

```json
{
  "sub_agents": [
    {
      "id": "sa_abc123",
      "name": "Research Agent",
      "role": "Searches the web and retrieves factual information",
      "tools": ["web_search", "wikipedia_lookup"],
      "model": "gpt-4o"
    },
    {
      "id": "sa_def456",
      "name": "Code Agent",
      "role": "Writes and reviews code, runs tests",
      "tools": ["code_executor", "file_reader", "test_runner"],
      "model": "claude-sonnet-4-20250514"
    }
  ]
}
```

This is injected into the master's system prompt so it can plan delegation:

```
You are a master orchestrator. You have the following team:

1. **Research Agent** — Searches the web and retrieves factual information.
   Available tools: web_search, wikipedia_lookup

2. **Code Agent** — Writes and reviews code, runs tests.
   Available tools: code_executor, file_reader, test_runner

When given a task, decide which agents to delegate to. You can delegate
to multiple agents in parallel. Collect their results and synthesize a
final answer.
```

---

## 9. Master Orchestration Strategy

The master uses a **delegate-collect-synthesize** loop:

```
1. PLAN       → Analyze task, decide which sub-agents to invoke
2. DELEGATE   → Send sub-tasks to selected sub-agents (parallel where possible)
3. WAIT       → Sub-agents execute in their lanes with their tools
4. COLLECT    → Gather results from completed sub-agent lanes
5. EVALUATE   → Check if task is complete
   ├─ YES → SYNTHESIZE final answer → DONE
   └─ NO  → Go to 1 (refine plan, delegate more)
```

This maps to a LangGraph state machine:

```python
# Simplified orchestration graph
builder = StateGraph(OrchestrationState)

builder.add_node("plan", plan_node)           # Master decides delegation
builder.add_node("delegate", delegate_node)   # Fans out to sub-agents
builder.add_node("collect", collect_node)      # Gathers lane results
builder.add_node("synthesize", synthesize_node)# Final answer

builder.set_entry_point("plan")
builder.add_edge("plan", "delegate")
builder.add_edge("delegate", "collect")
builder.add_conditional_edges("collect", should_continue, {
    "plan": "plan",         # Need more work
    "synthesize": "synthesize"  # Done
})
builder.add_edge("synthesize", END)
```

---

## 10. Shared Database Integration

NexAgent operates as **one microservice** in a larger ecosystem, sharing a PostgreSQL database.

**Rules:**
- All NexAgent tables live in the `nexagent` schema (avoids name collisions)
- Migrations managed via Alembic (schema-scoped)
- Connection string from environment: `DATABASE_URL`
- Async driver: `asyncpg`
- Never assume sole ownership of the database

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from nexagent.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

---

## 11. Security Considerations

| Concern | Approach |
|---|---|
| API key storage | Encrypted at rest (Fernet or similar), decrypted only at execution time |
| API key per sub-agent | Each sub-agent can have its own provider key |
| Input validation | Pydantic models on all API boundaries |
| Tool execution | Sandboxed — no arbitrary code execution by default |
| Database access | Schema-isolated, parameterized queries via ORM |
| Auth | JWT-based auth middleware (provided by gateway or added here) |

---

## 12. Future Considerations

- **Streaming execution updates** via WebSocket for live timeline rendering
- **Execution history + replay** for debugging workflows
- **Template workflows** (pre-configured agent trees for common tasks)
- **Conditional routing** in orchestration (if agent A fails, try agent B)
- **Human-in-the-loop** steps where execution pauses for user input
- **Cost tracking** per execution (token counts by sub-agent)
- **Rate limiting** per sub-agent to respect provider quotas
