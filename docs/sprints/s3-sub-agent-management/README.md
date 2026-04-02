# S3 — Sub-Agent Management

> **Milestone:** Layer 2 (Sub-Agents) fully configurable  
> **Goal:** Users can create sub-agents, assign them a model/provider, bind tools, and manage their lifecycle.  
> **Depends on:** S2 (Tool Management)

---

## Epics

### Epic 3.1: Sub-Agent ORM Models & Migration
> Implement `sub_agents` and `sub_agent_tools` tables.

- [ ] Flesh out `models/sub_agent.py` — all columns (name, role_description, system_prompt, provider, model_name, api_key_encrypted, temperature, max_tokens, config, is_active, timestamps)
- [ ] Create `models/sub_agent_tool.py` — join table (`sub_agent_id`, `tool_id`, `priority`)
- [ ] Add foreign key relationships with cascade deletes
- [ ] Define ORM relationship: `SubAgent.tools` ↔ `ToolDefinition.sub_agents`
- [ ] Create Alembic migration
- [ ] Model-level tests (create agent, assign tools, cascade delete)

**Acceptance Criteria:**
- Both tables created via migration
- Assigning/removing tools works via ORM relationship
- Deleting a sub-agent cascades to `sub_agent_tools`
- Deleting a tool cascades to `sub_agent_tools`

---

### Epic 3.2: Sub-Agent Pydantic Schemas
> Request/response schemas for sub-agent API.

- [ ] `schemas/sub_agents.py` — `SubAgentCreate`, `SubAgentUpdate`, `SubAgentRead`, `SubAgentList`
- [ ] `SubAgentCreate` accepts `tool_ids: list[UUID]` for initial tool binding
- [ ] `SubAgentRead` includes nested `tools: list[ToolRead]`
- [ ] Validate `provider` against known providers (`openai`, `anthropic`, `litellm`, `custom`)
- [ ] `api_key` accepted as plaintext in create/update, never returned in read responses

**Acceptance Criteria:**
- API key is write-only (never serialized in responses)
- Tool binding validated (referenced tools must exist)
- Provider enum validation with clear error for unknowns

---

### Epic 3.3: API Key Encryption
> Secure storage for per-agent API keys.

- [ ] Add `ENCRYPTION_KEY` to `config.py` Settings
- [ ] Create `src/nexagent/services/crypto.py` — `encrypt_api_key()`, `decrypt_api_key()` using Fernet symmetric encryption
- [ ] Integrate into sub-agent create/update flow: plaintext in → encrypted at rest
- [ ] Integrate into execution flow: decrypt only when invoking the LLM
- [ ] Test encryption round-trip
- [ ] Verify encrypted values are not logged anywhere

**Acceptance Criteria:**
- API keys stored as encrypted blobs in `api_key_encrypted`
- Decryption works correctly at execution time
- Missing `ENCRYPTION_KEY` raises clear startup error if encrypted keys exist

---

### Epic 3.4: Sub-Agent Service Layer
> Business logic for sub-agent management.

- [ ] `services/sub_agent_service.py` — `create_sub_agent()`, `get_sub_agent()`, `list_sub_agents()`, `update_sub_agent()`, `delete_sub_agent()`
- [ ] `bind_tools(sub_agent_id, tool_ids)` — replace tool bindings
- [ ] `add_tool(sub_agent_id, tool_id)` / `remove_tool(sub_agent_id, tool_id)` — incremental changes
- [ ] Validate referenced `tool_ids` exist and are active
- [ ] Encrypt API key on create/update
- [ ] Filter/search: by provider, by model, by active status

**Acceptance Criteria:**
- Full CRUD + tool binding operations work
- Referencing a non-existent tool returns 404/422
- API key encrypted before persistence

---

### Epic 3.5: Sub-Agent REST API Endpoints
> Expose sub-agent management via FastAPI routes.

- [ ] `api/sub_agents_router.py` — CRUD under `/api/v1/sub-agents`
- [ ] `POST /api/v1/sub-agents` — create with optional tool_ids
- [ ] `GET /api/v1/sub-agents` — list with filters
- [ ] `GET /api/v1/sub-agents/{id}` — detail with tool list
- [ ] `PUT /api/v1/sub-agents/{id}` — update agent config
- [ ] `DELETE /api/v1/sub-agents/{id}` — soft-delete
- [ ] `PUT /api/v1/sub-agents/{id}/tools` — replace tool bindings
- [ ] `POST /api/v1/sub-agents/{id}/tools/{tool_id}` — add single tool
- [ ] `DELETE /api/v1/sub-agents/{id}/tools/{tool_id}` — remove single tool
- [ ] Register router, integration tests

**Acceptance Criteria:**
- All endpoints return correct status codes
- Tool binding endpoints work for bulk and single operations
- API key never appears in any response body

---

### Epic 3.6: Model Provider Validation
> Verify that configured model/provider combos are reachable.

- [ ] `services/provider_validation.py` — `validate_provider(provider, model_name, api_key)` 
- [ ] Lightweight check: small prompt to verify the model responds (optional, on-demand)
- [ ] `POST /api/v1/sub-agents/{id}/validate` — test that the sub-agent's LLM config works
- [ ] Return clear error if provider unreachable or key invalid
- [ ] Do NOT run validation automatically on every create/update (only on explicit request)

**Acceptance Criteria:**
- `/validate` endpoint returns success/failure with clear message
- Invalid API key → clear "authentication failed" response
- Unknown model → clear "model not found" response
- Timeout after reasonable duration (10s)
