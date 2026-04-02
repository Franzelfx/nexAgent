# NexAgent — Database Model Blueprint

> Schema: `nexagent` (shared PostgreSQL instance)  
> ORM: SQLAlchemy 2.x (async)  
> Migrations: Alembic

---

## ER Overview

```
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│ tool_definitions │◄────┤ sub_agent_tools (m2m) ├────►│ sub_agents       │
└──────────────────┘     └──────────────────────┘     └────────┬─────────┘
                                                               │
                                                    ┌──────────┴──────────┐
                                                    │orchestrator_agents  │
                                                    │       (m2m)        │
                                                    └──────────┬──────────┘
                                                               │
                                                    ┌──────────▼─────────┐
                                                    │   orchestrators    │
                                                    └──────────┬─────────┘
                                                               │
                                                    ┌──────────▼─────────┐
                                                    │    workflows       │
                                                    └──────────┬─────────┘
                                                               │
                                                    ┌──────────▼─────────┐
                                                    │    executions      │
                                                    └──────────┬─────────┘
                                                               │
                                                    ┌──────────▼─────────┐
                                                    │  execution_lanes   │
                                                    └──────────┬─────────┘
                                                               │
                                                    ┌──────────▼─────────┐
                                                    │  execution_steps   │
                                                    └────────────────────┘
```

---

## Table Definitions

### 1. `nexagent.tool_definitions`

Reusable tool definitions. A tool is a callable capability attached to sub-agents.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Unique tool ID |
| `name` | `VARCHAR(255)` | NOT NULL, UNIQUE | Machine-readable name (e.g. `web_search`) |
| `display_name` | `VARCHAR(255)` | NOT NULL | Human-readable name |
| `description` | `TEXT` | NOT NULL | What the tool does (fed to LLM) |
| `tool_type` | `VARCHAR(50)` | NOT NULL | `builtin`, `api_call`, `function`, `mcp` |
| `input_schema` | `JSONB` | NOT NULL | JSON Schema for tool input |
| `output_schema` | `JSONB` | | JSON Schema for tool output (optional) |
| `config` | `JSONB` | | Type-specific config (URL, headers, code, etc.) |
| `is_active` | `BOOLEAN` | DEFAULT true | Soft-disable toggle |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

```sql
CREATE TABLE nexagent.tool_definitions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL UNIQUE,
    display_name  VARCHAR(255) NOT NULL,
    description   TEXT NOT NULL,
    tool_type     VARCHAR(50) NOT NULL CHECK (tool_type IN ('builtin', 'api_call', 'function', 'mcp')),
    input_schema  JSONB NOT NULL DEFAULT '{}',
    output_schema JSONB,
    config        JSONB DEFAULT '{}',
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 2. `nexagent.sub_agents`

A sub-agent is an LLM-backed worker with a specific role and set of tools.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | Unique sub-agent ID |
| `name` | `VARCHAR(255)` | NOT NULL | Display name |
| `role_description` | `TEXT` | NOT NULL | What this agent does (capability — fed to master) |
| `system_prompt` | `TEXT` | | Custom system prompt for this agent |
| `provider` | `VARCHAR(50)` | NOT NULL | `openai`, `anthropic`, `litellm`, etc. |
| `model_name` | `VARCHAR(255)` | NOT NULL | e.g. `gpt-4o`, `claude-sonnet-4-20250514` |
| `api_key_encrypted` | `TEXT` | | Encrypted provider API key |
| `temperature` | `FLOAT` | DEFAULT 0.0 | LLM temperature |
| `max_tokens` | `INTEGER` | | Max response tokens |
| `config` | `JSONB` | DEFAULT `{}` | Additional model params |
| `is_active` | `BOOLEAN` | DEFAULT true | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | |

```sql
CREATE TABLE nexagent.sub_agents (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name               VARCHAR(255) NOT NULL,
    role_description   TEXT NOT NULL,
    system_prompt      TEXT,
    provider           VARCHAR(50) NOT NULL,
    model_name         VARCHAR(255) NOT NULL,
    api_key_encrypted  TEXT,
    temperature        DOUBLE PRECISION DEFAULT 0.0,
    max_tokens         INTEGER,
    config             JSONB DEFAULT '{}',
    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 3. `nexagent.sub_agent_tools` (Join Table)

Links tools to sub-agents (many-to-many).

| Column | Type | Constraints |
|---|---|---|
| `sub_agent_id` | `UUID` | FK → sub_agents.id, ON DELETE CASCADE |
| `tool_id` | `UUID` | FK → tool_definitions.id, ON DELETE CASCADE |
| `priority` | `INTEGER` | DEFAULT 0 (ordering hint) |

```sql
CREATE TABLE nexagent.sub_agent_tools (
    sub_agent_id UUID NOT NULL REFERENCES nexagent.sub_agents(id) ON DELETE CASCADE,
    tool_id      UUID NOT NULL REFERENCES nexagent.tool_definitions(id) ON DELETE CASCADE,
    priority     INTEGER DEFAULT 0,
    PRIMARY KEY (sub_agent_id, tool_id)
);
```

---

### 4. `nexagent.orchestrators`

The master orchestrator — one per workflow. Knows its sub-agents.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `name` | `VARCHAR(255)` | NOT NULL | |
| `description` | `TEXT` | | Purpose of this orchestrator |
| `system_prompt` | `TEXT` | | Master system prompt template |
| `provider` | `VARCHAR(50)` | NOT NULL | |
| `model_name` | `VARCHAR(255)` | NOT NULL | |
| `api_key_encrypted` | `TEXT` | | |
| `temperature` | `FLOAT` | DEFAULT 0.0 | |
| `max_tokens` | `INTEGER` | | |
| `strategy` | `VARCHAR(50)` | DEFAULT `parallel` | `parallel`, `sequential`, `adaptive` |
| `max_iterations` | `INTEGER` | DEFAULT 5 | Max plan-delegate-collect loops |
| `config` | `JSONB` | DEFAULT `{}` | |
| `is_active` | `BOOLEAN` | DEFAULT true | |
| `created_at` | `TIMESTAMPTZ` | | |
| `updated_at` | `TIMESTAMPTZ` | | |

```sql
CREATE TABLE nexagent.orchestrators (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(255) NOT NULL,
    description       TEXT,
    system_prompt     TEXT,
    provider          VARCHAR(50) NOT NULL,
    model_name        VARCHAR(255) NOT NULL,
    api_key_encrypted TEXT,
    temperature       DOUBLE PRECISION DEFAULT 0.0,
    max_tokens        INTEGER,
    strategy          VARCHAR(50) DEFAULT 'parallel' CHECK (strategy IN ('parallel', 'sequential', 'adaptive')),
    max_iterations    INTEGER DEFAULT 5,
    config            JSONB DEFAULT '{}',
    is_active         BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 5. `nexagent.orchestrator_sub_agents` (Join Table)

Links sub-agents to an orchestrator (many-to-many).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `orchestrator_id` | `UUID` | FK → orchestrators.id, ON DELETE CASCADE | |
| `sub_agent_id` | `UUID` | FK → sub_agents.id, ON DELETE CASCADE | |
| `priority` | `INTEGER` | DEFAULT 0 | Ordering / preference |

```sql
CREATE TABLE nexagent.orchestrator_sub_agents (
    orchestrator_id UUID NOT NULL REFERENCES nexagent.orchestrators(id) ON DELETE CASCADE,
    sub_agent_id    UUID NOT NULL REFERENCES nexagent.sub_agents(id) ON DELETE CASCADE,
    priority        INTEGER DEFAULT 0,
    PRIMARY KEY (orchestrator_id, sub_agent_id)
);
```

---

### 6. `nexagent.workflows`

A workflow is a saved, named configuration snapshot — an orchestrator with its full tree.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `name` | `VARCHAR(255)` | NOT NULL | |
| `description` | `TEXT` | | |
| `orchestrator_id` | `UUID` | FK → orchestrators.id | Root of the tree |
| `graph_layout` | `JSONB` | | UI node positions for drag-and-drop builder |
| `is_active` | `BOOLEAN` | DEFAULT true | |
| `created_at` | `TIMESTAMPTZ` | | |
| `updated_at` | `TIMESTAMPTZ` | | |

```sql
CREATE TABLE nexagent.workflows (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(255) NOT NULL,
    description      TEXT,
    orchestrator_id  UUID REFERENCES nexagent.orchestrators(id) ON DELETE SET NULL,
    graph_layout     JSONB DEFAULT '{}',
    is_active        BOOLEAN NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 7. `nexagent.executions`

A single run of a workflow — tracks from task input to final output.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `workflow_id` | `UUID` | FK → workflows.id | Which workflow was executed |
| `task_input` | `TEXT` | NOT NULL | The instruction given to the master |
| `final_output` | `TEXT` | | Synthesized result |
| `status` | `VARCHAR(30)` | NOT NULL | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `error_message` | `TEXT` | | If failed |
| `total_tokens` | `INTEGER` | DEFAULT 0 | Aggregate token usage |
| `total_cost_usd` | `NUMERIC(10,6)` | | Estimated cost |
| `started_at` | `TIMESTAMPTZ` | | |
| `finished_at` | `TIMESTAMPTZ` | | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | |

```sql
CREATE TABLE nexagent.executions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id    UUID REFERENCES nexagent.workflows(id) ON DELETE SET NULL,
    task_input     TEXT NOT NULL,
    final_output   TEXT,
    status         VARCHAR(30) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    error_message  TEXT,
    total_tokens   INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10, 6),
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_executions_workflow ON nexagent.executions(workflow_id);
CREATE INDEX idx_executions_status ON nexagent.executions(status);
```

---

### 8. `nexagent.execution_lanes`

One lane per actor in a single execution — maps to the "guitar" visualization rows.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `execution_id` | `UUID` | FK → executions.id, ON DELETE CASCADE | |
| `lane_index` | `INTEGER` | NOT NULL | 0 = master, 1+ = sub-agents |
| `actor_type` | `VARCHAR(30)` | NOT NULL | `master` or `sub_agent` |
| `actor_id` | `UUID` | | FK-like ref to orchestrator or sub-agent |
| `actor_name` | `VARCHAR(255)` | NOT NULL | Denormalized for fast reads |
| `status` | `VARCHAR(30)` | NOT NULL | `pending`, `running`, `completed`, `failed` |
| `started_at` | `TIMESTAMPTZ` | | |
| `finished_at` | `TIMESTAMPTZ` | | |

```sql
CREATE TABLE nexagent.execution_lanes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id  UUID NOT NULL REFERENCES nexagent.executions(id) ON DELETE CASCADE,
    lane_index    INTEGER NOT NULL,
    actor_type    VARCHAR(30) NOT NULL CHECK (actor_type IN ('master', 'sub_agent')),
    actor_id      UUID,
    actor_name    VARCHAR(255) NOT NULL,
    status        VARCHAR(30) NOT NULL DEFAULT 'pending',
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    UNIQUE (execution_id, lane_index)
);
```

---

### 9. `nexagent.execution_steps`

Individual steps within a lane — the finest-grained execution record.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK | |
| `lane_id` | `UUID` | FK → execution_lanes.id, ON DELETE CASCADE | |
| `step_index` | `INTEGER` | NOT NULL | Order within the lane |
| `step_type` | `VARCHAR(30)` | NOT NULL | `llm_call`, `tool_call`, `delegation`, `synthesis`, `error` |
| `input_data` | `JSONB` | | What was sent (prompt, tool args, etc.) |
| `output_data` | `JSONB` | | What came back |
| `model_used` | `VARCHAR(255)` | | Which model was called |
| `tokens_prompt` | `INTEGER` | | |
| `tokens_completion` | `INTEGER` | | |
| `duration_ms` | `INTEGER` | | Wall-clock time in milliseconds |
| `status` | `VARCHAR(30)` | NOT NULL | `running`, `completed`, `failed` |
| `error_message` | `TEXT` | | |
| `started_at` | `TIMESTAMPTZ` | | |
| `finished_at` | `TIMESTAMPTZ` | | |

```sql
CREATE TABLE nexagent.execution_steps (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lane_id           UUID NOT NULL REFERENCES nexagent.execution_lanes(id) ON DELETE CASCADE,
    step_index        INTEGER NOT NULL,
    step_type         VARCHAR(30) NOT NULL
                       CHECK (step_type IN ('llm_call', 'tool_call', 'delegation', 'synthesis', 'error')),
    input_data        JSONB,
    output_data       JSONB,
    model_used        VARCHAR(255),
    tokens_prompt     INTEGER,
    tokens_completion INTEGER,
    duration_ms       INTEGER,
    status            VARCHAR(30) NOT NULL DEFAULT 'running',
    error_message     TEXT,
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    UNIQUE (lane_id, step_index)
);

CREATE INDEX idx_execution_steps_lane ON nexagent.execution_steps(lane_id);
```

---

## Indexes Summary

| Table | Index | Purpose |
|---|---|---|
| `executions` | `workflow_id` | Lookup executions by workflow |
| `executions` | `status` | Filter running/pending executions |
| `execution_steps` | `lane_id` | Fast lane step retrieval for timeline |
| `execution_lanes` | `(execution_id, lane_index)` UNIQUE | One lane per index per execution |
| `execution_steps` | `(lane_id, step_index)` UNIQUE | Ordered steps within lane |

---

## Migration Strategy

```
alembic/
├── env.py              # target_metadata from nexagent.models.base
├── script.py.mako
└── versions/
    ├── 001_create_nexagent_schema.py
    ├── 002_tool_definitions.py
    ├── 003_sub_agents_and_tools.py
    ├── 004_orchestrators.py
    ├── 005_workflows.py
    └── 006_executions_lanes_steps.py
```

First migration creates the schema:
```sql
CREATE SCHEMA IF NOT EXISTS nexagent;
```

---

## SQLAlchemy Model Example

```python
# models/base.py
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

class Base(DeclarativeBase):
    __table_args__ = {"schema": "nexagent"}
```

```python
# models/sub_agent.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from nexagent.models.base import Base

class SubAgent(Base):
    __tablename__ = "sub_agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_description: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tools = relationship("ToolDefinition", secondary="nexagent.sub_agent_tools", back_populates="sub_agents")
```

---

## Query Patterns

**Get full execution timeline (for guitar view):**
```sql
SELECT
    l.lane_index,
    l.actor_name,
    l.actor_type,
    s.step_index,
    s.step_type,
    s.status,
    s.started_at,
    s.finished_at,
    s.duration_ms
FROM nexagent.execution_lanes l
JOIN nexagent.execution_steps s ON s.lane_id = l.id
WHERE l.execution_id = :execution_id
ORDER BY l.lane_index, s.step_index;
```

**Build capability map for master prompt:**
```sql
SELECT
    sa.id,
    sa.name,
    sa.role_description,
    array_agg(td.name ORDER BY sat.priority) AS tool_names,
    array_agg(td.description ORDER BY sat.priority) AS tool_descriptions
FROM nexagent.orchestrator_sub_agents osa
JOIN nexagent.sub_agents sa ON sa.id = osa.sub_agent_id
LEFT JOIN nexagent.sub_agent_tools sat ON sat.sub_agent_id = sa.id
LEFT JOIN nexagent.tool_definitions td ON td.id = sat.tool_id
WHERE osa.orchestrator_id = :orchestrator_id
  AND sa.is_active = true
GROUP BY sa.id, sa.name, sa.role_description
ORDER BY osa.priority;
```
