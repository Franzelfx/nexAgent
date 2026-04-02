# S6 — Timeline & Observability

> **Milestone:** Full execution visibility — the "guitar view"  
> **Goal:** Every execution is tracked step-by-step with lanes, enabling the timeline visualization UI. Live streaming via WebSocket.  
> **Depends on:** S5 (Execution Engine)

---

## Epics

### Epic 6.1: Execution Persistence Models & Migration
> Implement `executions`, `execution_lanes`, and `execution_steps` tables.

- [ ] Flesh out `models/execution.py` — executions table (workflow_id, task_input, final_output, status, error_message, total_tokens, total_cost_usd, started_at, finished_at)
- [ ] Create `models/execution_lane.py` — lanes table (execution_id, lane_index, actor_type, actor_id, actor_name, status, timestamps)
- [ ] Create `models/execution_step.py` — steps table (lane_id, step_index, step_type, input_data, output_data, model_used, tokens_prompt, tokens_completion, duration_ms, status, error_message, timestamps)
- [ ] All indexes from DATABASE.md blueprint
- [ ] Unique constraints: `(execution_id, lane_index)`, `(lane_id, step_index)`
- [ ] Alembic migration
- [ ] Model tests

**Acceptance Criteria:**
- All three tables created with proper relationships and indexes
- Cascade deletes: execution → lanes → steps
- Unique constraints prevent duplicate lane/step entries

---

### Epic 6.2: Execution Tracker Service
> Record every step of an execution as it happens.

- [ ] `services/execution_service.py` — extends with tracking functions
- [ ] `create_execution(workflow_id, task_input)` → creates execution + master lane (index 0)
- [ ] `create_lane(execution_id, actor_type, actor_id, actor_name)` → adds sub-agent lane
- [ ] `record_step(lane_id, step_type, input_data, output_data, ...)` → appends step to lane
- [ ] `complete_lane(lane_id, status)` / `complete_execution(execution_id, final_output, status)`
- [ ] Token aggregation: sum step tokens into lane/execution totals
- [ ] Integrate tracker calls into `master_runner`, `sub_agent_runner`, `tool_executor`

**Acceptance Criteria:**
- Every LLM call, tool call, delegation, and synthesis is recorded as a step
- Lane statuses update as sub-agents start/finish
- Execution status reflects overall progress
- Token counts aggregated correctly

---

### Epic 6.3: Timeline API
> Serve the lane-based timeline data for the "guitar view" frontend.

- [ ] `GET /api/v1/executions/{id}/timeline` — returns structured timeline
- [ ] Response format: list of lanes, each with ordered steps and timing data
- [ ] Include: lane metadata (actor name, type), step details (type, status, duration, timestamps)
- [ ] Pydantic schemas: `TimelineLane`, `TimelineStep`, `TimelineResponse`
- [ ] Optimized query: single JOIN query from lanes + steps (see DATABASE.md query patterns)
- [ ] Support `?include_data=true` param to include full input/output JSONB (default: omit for performance)

**Acceptance Criteria:**
- Timeline returns correct lane/step structure for a completed execution
- Steps ordered by `step_index` within each lane
- Lanes ordered by `lane_index`
- Without `include_data`, response is lightweight (no large JSONB payloads)
- With `include_data`, full input/output included

---

### Epic 6.4: WebSocket Live Execution Stream
> Real-time execution updates pushed to the frontend via WebSocket.

- [ ] `WS /api/v1/executions/{id}/live` — WebSocket endpoint
- [ ] Streams events as they happen: `lane_started`, `step_started`, `step_completed`, `lane_completed`, `execution_completed`, `execution_failed`
- [ ] Event format: `{event_type, lane_index, step_index, data, timestamp}`
- [ ] Engine hooks: fire events in master_runner, sub_agent_runner, tool_executor
- [ ] In-memory pub/sub (simple asyncio Event / Queue per execution)
- [ ] Client can connect after execution starts and receive in-progress state + live updates
- [ ] Graceful disconnect handling

**Acceptance Criteria:**
- Client receives real-time events during execution
- Late-joining clients get current state catch-up + live stream
- Disconnected clients don't cause errors in the engine
- Message format is JSON, parseable by frontend

---

### Epic 6.5: Token & Cost Tracking
> Track LLM token usage and estimated cost per execution.

- [ ] Record `tokens_prompt` and `tokens_completion` on every LLM step
- [ ] Cost estimation: configurable cost-per-token per provider/model (in config or DB)
- [ ] Aggregate per lane and per execution
- [ ] `GET /api/v1/executions/{id}` includes `total_tokens` and `total_cost_usd`
- [ ] `GET /api/v1/executions?workflow_id=X` summary includes usage stats

**Acceptance Criteria:**
- Token counts recorded on every LLM call step
- Cost estimated based on model pricing
- Aggregation correct across lanes and steps
- Summary available in execution list and detail

---

### Epic 6.6: Execution History & Filtering
> Full execution history with rich filtering for the UI.

- [ ] `GET /api/v1/executions` supports: filter by `workflow_id`, `status`, date range, sort by created/cost/tokens
- [ ] Pagination (offset + limit)
- [ ] Summary stats per execution (lane count, step count, total duration)
- [ ] `DELETE /api/v1/executions/{id}` — hard-delete for cleanup (cascades to lanes and steps)

**Acceptance Criteria:**
- Filtering and pagination work correctly
- Summary stats computed efficiently (aggregation queries)
- Delete cascades fully, no orphan rows
