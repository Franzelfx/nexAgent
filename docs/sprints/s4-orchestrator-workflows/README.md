# S4 — Orchestrator & Workflows

> **Milestone:** Layer 1 (Master Orchestrator) + full workflow configuration complete  
> **Goal:** Users can create master orchestrators, attach sub-agents, build capability maps, and save full workflows.  
> **Depends on:** S3 (Sub-Agent Management)

---

## Epics

### Epic 4.1: Orchestrator ORM Models & Migration
> Implement `orchestrators` and `orchestrator_sub_agents` tables.

- [ ] Flesh out `models/orchestrator.py` — all columns (name, description, system_prompt, provider, model_name, api_key_encrypted, temperature, max_tokens, strategy, max_iterations, config, is_active, timestamps)
- [ ] Create `models/orchestrator_sub_agent.py` — join table with priority
- [ ] Add `CHECK` constraint for `strategy` (`parallel`, `sequential`, `adaptive`)
- [ ] ORM relationships: `Orchestrator.sub_agents` ↔ `SubAgent.orchestrators`
- [ ] Alembic migration
- [ ] Model-level tests

**Acceptance Criteria:**
- Both tables created, relationships work
- Strategy constraint enforced at DB level
- Cascade behavior correct on deletions

---

### Epic 4.2: Workflow ORM Model & Migration
> Implement `workflows` table — a saved configuration snapshot.

- [ ] Flesh out `models/workflow.py` — all columns (name, description, orchestrator_id, graph_layout, is_active, timestamps)
- [ ] Foreign key to `orchestrators` with `ON DELETE SET NULL`
- [ ] `graph_layout` stores JSONB for UI node positions (drag-and-drop builder state)
- [ ] Alembic migration
- [ ] Model tests

**Acceptance Criteria:**
- Workflow references an orchestrator
- Deleting an orchestrator sets `orchestrator_id` to NULL (preserves workflow record)
- `graph_layout` accepts arbitrary JSON

---

### Epic 4.3: Orchestrator Pydantic Schemas
> Request/response schemas for orchestrator and workflow APIs.

- [ ] `schemas/orchestrators.py` — `OrchestratorCreate`, `OrchestratorUpdate`, `OrchestratorRead` (includes sub-agent summaries)
- [ ] `schemas/workflows.py` — `WorkflowCreate`, `WorkflowUpdate`, `WorkflowRead`, `WorkflowGraphExport`
- [ ] `OrchestratorRead` includes `capability_map` (auto-generated from sub-agents + their tools)
- [ ] `WorkflowGraphExport` returns the full node/edge representation for the UI builder

**Acceptance Criteria:**
- Capability map correctly lists all sub-agents with their tools
- Graph export contains nodes, edges, and layout positions
- API key fields are write-only

---

### Epic 4.4: Capability Map Builder
> Auto-generate the capability description that the master uses to know its team.

- [ ] `engine/capability_map.py` — `build_capability_map(orchestrator_id)` 
- [ ] Queries orchestrator → sub-agents → tools, builds structured description
- [ ] Outputs: JSON structure + natural language summary (for system prompt injection)
- [ ] Caches capability map (invalidated on sub-agent/tool changes)
- [ ] Tests with various configurations (0 agents, 1 agent, many agents, agents with no tools)

**Acceptance Criteria:**
- Capability map correctly reflects current configuration
- Natural language format suitable for LLM system prompt injection
- Empty cases handled gracefully

---

### Epic 4.5: Orchestrator & Workflow Service Layers
> Business logic for orchestrator and workflow management.

- [ ] `services/orchestrator_service.py` — full CRUD + sub-agent binding
- [ ] `bind_sub_agents(orchestrator_id, sub_agent_ids)` — replace bindings
- [ ] `add_sub_agent()` / `remove_sub_agent()` — incremental
- [ ] `get_capability_map(orchestrator_id)` — delegates to capability_map builder
- [ ] `services/workflow_service.py` — full CRUD
- [ ] `assemble_workflow(workflow_id)` — load full tree (orchestrator + agents + tools) for execution
- [ ] `export_graph(workflow_id)` — produce node/edge JSON for the UI

**Acceptance Criteria:**
- Orchestrator CRUD works with sub-agent management
- Workflow assembly loads the complete 3-layer tree
- Graph export matches expected UI format

---

### Epic 4.6: Orchestrator & Workflow REST API
> FastAPI routes for configuration management.

- [ ] `api/orchestrators_router.py` — CRUD under `/api/v1/orchestrators`
- [ ] `GET /api/v1/orchestrators/{id}` — includes capability map
- [ ] `PUT /api/v1/orchestrators/{id}/sub-agents` — manage sub-agent bindings
- [ ] `api/workflows_router.py` — CRUD under `/api/v1/workflows`
- [ ] `POST /api/v1/workflows` — create workflow (optionally creates orchestrator inline)
- [ ] `GET /api/v1/workflows/{id}/graph` — returns node/edge graph for UI builder
- [ ] Register routers, integration tests

**Acceptance Criteria:**
- All endpoints function correctly
- Capability map included in orchestrator detail response
- Graph endpoint returns UI-ready structure
- Proper error handling for invalid references

---

### Epic 4.7: Workflow Validation
> Ensure a workflow is complete and executable before it can be run.

- [ ] `services/workflow_service.py` — `validate_workflow(workflow_id)`
- [ ] Checks: orchestrator exists, has at least one sub-agent, all sub-agents have model config, all referenced tools are active
- [ ] Returns structured validation result: `{valid: bool, errors: [...]}`
- [ ] `POST /api/v1/workflows/{id}/validate` endpoint
- [ ] Validation runs automatically before execution (in S5)

**Acceptance Criteria:**
- Invalid workflows produce clear error messages
- Validation catches: missing orchestrator, agents without tools, inactive tools
- Valid workflows return clean pass
