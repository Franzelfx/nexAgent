# NexAgent — Sprint Planning

> Organized by milestone / major application feature.  
> Each sprint folder contains a README with epics and their breakdown.

---

## Sprint Overview

| Sprint | Milestone | Focus |
|---|---|---|
| [S1 — Foundation](./s1-foundation/) | Project skeleton, DB, config | Database setup, models, Alembic migrations, shared-DB integration |
| [S2 — Tool Management](./s2-tool-management/) | Layer 3 complete | Tool definition CRUD, built-in tools, tool registry |
| [S3 — Sub-Agent Management](./s3-sub-agent-management/) | Layer 2 complete | Sub-agent CRUD, tool binding, model provider config |
| [S4 — Orchestrator & Workflows](./s4-orchestrator-workflows/) | Layer 1 + Config complete | Orchestrator CRUD, capability map, workflow assembly, graph export |
| [S5 — Execution Engine](./s5-execution-engine/) | Core runtime | Master runner, sub-agent runner, lane manager, delegation loop |
| [S6 — Timeline & Observability](./s6-timeline-observability/) | Visibility | Execution tracking, timeline API, WebSocket live stream, token/cost tracking |
| [S7 — Security & Production](./s7-security-production/) | Production-ready | API key encryption, auth middleware, rate limiting, hardening |

---

## How to Use This Structure

- Each sprint folder has a `README.md` listing all **epics** for that milestone
- Epics are described with scope, acceptance criteria, and key tasks
- Sprints are sequential — each builds on the previous
- Within a sprint, epics can be worked in parallel where dependencies allow
- Mark epic status inline as work progresses: `[ ]` → `[x]`

## Relationship to Blueprint

These sprints implement the architecture defined in:
- [Architecture Blueprint](../blueprint/ARCHITECTURE.md)
- [Database Model Blueprint](../blueprint/DATABASE.md)
