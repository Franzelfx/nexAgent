# S5 — Execution Engine

> **Milestone:** Core orchestration runtime operational  
> **Goal:** A configured workflow can receive a task, the master plans and delegates to sub-agents, sub-agents use tools, results are collected and synthesized.  
> **Depends on:** S4 (Orchestrator & Workflows)

---

## Epics

### Epic 5.1: Orchestration State Definition
> Define the state that flows through the multi-agent execution graph.

- [ ] `state/orchestration.py` — `OrchestrationState` Pydantic model
- [ ] Fields: `task_input`, `plan` (master's current delegation plan), `delegations` (list of sub-tasks with assigned agent), `lane_results` (collected outputs per lane), `final_output`, `iteration_count`, `status`
- [ ] Reducers for list fields (append-only via `operator.add`)
- [ ] Sub-state: `DelegationTask` — `sub_agent_id`, `sub_task`, `status`, `result`
- [ ] Tests for state transitions and reducer behavior

**Acceptance Criteria:**
- State captures the full lifecycle from task input to final output
- Reducers correctly accumulate delegations and results
- Serializable to/from JSON for persistence

---

### Epic 5.2: Master Runner (LangGraph)
> The master orchestrator as a LangGraph state machine: plan → delegate → collect → synthesize.

- [ ] `engine/master_runner.py` — builds a LangGraph `StateGraph` per workflow execution
- [ ] `plan_node` — master LLM analyzes task + capability map, produces delegation plan
- [ ] `delegate_node` — fans out sub-tasks to sub-agent runners
- [ ] `collect_node` — gathers results from completed sub-agent executions
- [ ] `evaluate_edge` — conditional: need more work → plan again, or → synthesize
- [ ] `synthesize_node` — master LLM produces final answer from collected results
- [ ] Respect `max_iterations` from orchestrator config
- [ ] Pass capability map into master system prompt

**Acceptance Criteria:**
- Master correctly plans delegation based on capability map
- Delegation plan references valid sub-agent IDs
- Synthesis produces coherent output from multiple sub-agent results
- Loop terminates after max_iterations even if task isn't "done"

---

### Epic 5.3: Sub-Agent Runner
> Each sub-agent runs its own isolated ReAct loop with its bound tools.

- [ ] `engine/sub_agent_runner.py` — `run_sub_agent(sub_agent_id, sub_task, tools)`
- [ ] Dynamically builds an LLM instance from the sub-agent's provider/model/key config
- [ ] Binds only the tools assigned to this sub-agent
- [ ] Runs a standard ReAct loop (LLM → tool calls → LLM → ... → final answer)
- [ ] Returns structured result: `{output, tool_calls_log, tokens_used, duration_ms}`
- [ ] Respects sub-agent-level settings (temperature, max_tokens, system_prompt)
- [ ] Error handling: LLM failures, tool failures, timeouts

**Acceptance Criteria:**
- Sub-agent uses only its configured model and tools
- Failed tool calls don't crash the entire execution
- Result includes full trace of LLM and tool invocations
- API key correctly decrypted at runtime

---

### Epic 5.4: Tool Executor
> Resolve tool definitions from DB and execute them at runtime.

- [ ] `engine/tool_executor.py` — converts `tool_definitions` DB records into LangChain `@tool` callables
- [ ] Support `builtin` type: map to existing Python functions in `tools/__init__.py`
- [ ] Support `api_call` type: make HTTP request based on tool config (URL, method, headers)
- [ ] Support `function` type: (future — sandboxed code execution, stub for now)
- [ ] Support `mcp` type: (future — MCP protocol integration, stub for now)
- [ ] Cache resolved tools per execution (don't re-resolve on every call)
- [ ] Tests for each tool type resolution

**Acceptance Criteria:**
- Built-in tools resolve and execute correctly
- API call tools make proper HTTP requests and return results
- Unknown tool types raise clear errors
- Stubs for `function` and `mcp` types return "not implemented" gracefully

---

### Epic 5.5: Lane Manager
> Coordinate parallel sub-agent executions as lanes.

- [ ] `engine/lane_manager.py` — manages concurrent sub-agent runs for a single execution
- [ ] `execute_delegations(delegations: list[DelegationTask])` — runs sub-agents in parallel (asyncio)
- [ ] Strategy support: `parallel` (all at once), `sequential` (one by one), `adaptive` (master decides)
- [ ] Collects results as lanes complete
- [ ] Handles partial failures: if one sub-agent fails, others continue
- [ ] Reports lane status in real-time (for future WebSocket streaming)

**Acceptance Criteria:**
- Parallel strategy runs all sub-agents concurrently
- Sequential strategy runs one at a time in priority order
- One failing sub-agent doesn't abort the others
- All results collected with proper lane indexing

---

### Epic 5.6: Execution API Endpoints
> Trigger and monitor workflow executions.

- [ ] `api/executions_router.py` under `/api/v1/execute` and `/api/v1/executions`
- [ ] `POST /api/v1/execute` — `{workflow_id, task_input}` → starts execution, returns execution ID
- [ ] `GET /api/v1/executions` — list executions (filter by workflow, status)
- [ ] `GET /api/v1/executions/{id}` — full execution detail with lane results
- [ ] `POST /api/v1/executions/{id}/cancel` — cancel running execution
- [ ] Execution runs asynchronously (background task), endpoint returns immediately
- [ ] Validate workflow before execution (from Epic 4.7)
- [ ] Register router, integration tests

**Acceptance Criteria:**
- Execution starts in background, returns `202 Accepted` with execution ID
- Polling `GET /executions/{id}` shows status progression
- Cancel actually stops running sub-agents
- Invalid workflow returns 422 with validation errors

---

### Epic 5.7: Backward Compatibility — `/chat` Endpoint
> Ensure the existing simple `/chat` endpoint still works.

- [ ] Keep `/chat` as a direct single-agent call (no orchestration overhead)
- [ ] Optionally: add a `workflow_id` parameter to `/chat` that routes through orchestration
- [ ] Existing tests for `/chat` continue to pass
- [ ] Document both paths in README

**Acceptance Criteria:**
- `POST /chat {message}` works exactly as before
- No regression in existing behavior
