# S2 — Tool Management

> **Milestone:** Layer 3 (Tools) fully configurable  
> **Goal:** Users can create, read, update, delete tool definitions that will later be bound to sub-agents.  
> **Depends on:** S1 (Foundation)

---

## Epics

### Epic 2.1: Tool Definition ORM Model & Migration
> Implement the `tool_definitions` table from the database blueprint.

- [ ] Flesh out `models/tool_definition.py` with all columns (name, display_name, description, tool_type, input_schema, output_schema, config, is_active, timestamps)
- [ ] Add `CHECK` constraint for `tool_type` (`builtin`, `api_call`, `function`, `mcp`)
- [ ] Add unique constraint on `name`
- [ ] Create Alembic migration for `nexagent.tool_definitions`
- [ ] Run migration and verify table exists with correct schema
- [ ] Write model-level tests (create, read, unique constraint violation)

**Acceptance Criteria:**
- `nexagent.tool_definitions` table created via migration
- ORM model correctly maps all columns
- Unique name constraint enforced

---

### Epic 2.2: Tool Pydantic Schemas
> Define request/response schemas for the tools API.

- [ ] `schemas/tools.py` — `ToolCreate` (input for POST), `ToolUpdate` (input for PUT, all optional), `ToolRead` (response), `ToolList` (paginated list response)
- [ ] Validate `input_schema` is valid JSON Schema (basic structure check)
- [ ] Validate `tool_type` enum values
- [ ] Add examples to schema fields for OpenAPI docs

**Acceptance Criteria:**
- Schemas pass validation for valid input
- Invalid tool_type or malformed input_schema rejected with clear error
- OpenAPI docs show example payloads

---

### Epic 2.3: Tool Service Layer
> Business logic for tool CRUD operations.

- [ ] `services/tool_service.py` — `create_tool()`, `get_tool()`, `list_tools()`, `update_tool()`, `delete_tool()`
- [ ] Soft-delete via `is_active = false` (preserve references from existing sub-agents)
- [ ] Duplicate name detection with clear error message
- [ ] Filter/search: by `tool_type`, by `is_active`, by name substring
- [ ] Unit tests for service functions (mocked DB session)

**Acceptance Criteria:**
- All CRUD operations work correctly
- Soft-delete doesn't break foreign key references
- Filtering returns correct subsets

---

### Epic 2.4: Tool REST API Endpoints
> Expose tool management via FastAPI routes.

- [ ] `api/tools_router.py` with all CRUD endpoints under `/api/v1/tools`
- [ ] `POST /api/v1/tools` — create tool definition
- [ ] `GET /api/v1/tools` — list tools (with filters: type, active, search)
- [ ] `GET /api/v1/tools/{id}` — get single tool
- [ ] `PUT /api/v1/tools/{id}` — update tool
- [ ] `DELETE /api/v1/tools/{id}` — soft-delete tool
- [ ] Register router in `api/__init__.py`
- [ ] Integration tests: full request → response cycle

**Acceptance Criteria:**
- All endpoints return correct status codes (201, 200, 404, 409, 422)
- Pagination works on list endpoint
- OpenAPI docs render correctly for all endpoints

---

### Epic 2.5: Built-in Tool Registration
> Seed the database with built-in tools and sync them on startup.

- [ ] Define built-in tools (current: `get_current_time`, `calculator`) as seed data
- [ ] On app startup, upsert built-in tool definitions into `tool_definitions` table
- [ ] Mark built-in tools with `tool_type = 'builtin'` — prevent deletion via API
- [ ] Ensure `tools/__init__.py` ALL_TOOLS registry stays in sync with DB
- [ ] Test that startup seeding is idempotent

**Acceptance Criteria:**
- Built-in tools appear in `GET /api/v1/tools` after startup
- Built-in tools cannot be deleted (409 or 403 response)
- Adding a new built-in tool in code auto-registers it in DB on next startup
