# S1 — Foundation

> **Milestone:** Project skeleton, database setup, shared-DB integration  
> **Goal:** Establish the base infrastructure so all subsequent sprints can build on a working DB layer, config system, and project structure.

---

## Epics

### Epic 1.1: Project Structure Expansion
> Set up the target module layout from the architecture blueprint.

- [ ] Create `src/nexagent/models/` package with `base.py` (DeclarativeBase, `nexagent` schema)
- [ ] Create `src/nexagent/schemas/` package (empty init, ready for Pydantic schemas)
- [ ] Create `src/nexagent/services/` package (empty init, ready for business logic)
- [ ] Create `src/nexagent/engine/` package (empty init, ready for orchestration runtime)
- [ ] Verify existing packages (`agents/`, `api/`, `graphs/`, `state/`, `tools/`) are untouched
- [ ] Ensure `pyproject.toml` includes new dependencies (`sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `cryptography`)

**Acceptance Criteria:**
- All new packages importable without errors
- Existing tests still pass
- No circular imports

---

### Epic 1.2: Database Connection & Config
> Add PostgreSQL async connection using SQLAlchemy 2.x, configured via environment.

- [ ] Add `DATABASE_URL` to `config.py` Settings (with sensible default for local dev)
- [ ] Create `src/nexagent/database.py` — async engine, session factory, `get_db` dependency
- [ ] Add connection pool settings to config (pool size, overflow, timeout)
- [ ] Create `nexagent` schema on startup if it doesn't exist
- [ ] Add health check that verifies DB connectivity (`/health` returns DB status)
- [ ] Update `docker-compose.dev.yml` to include a PostgreSQL service

**Acceptance Criteria:**
- App starts and connects to PostgreSQL
- `/health` shows `"db": "ok"` when connected
- Config works with both direct URL and env variables

---

### Epic 1.3: Alembic Migration Setup
> Configure Alembic for schema-scoped migrations in the shared database.

- [ ] Initialize Alembic with async support (`alembic init -t async`)
- [ ] Configure `env.py` to target `nexagent` schema using model metadata
- [ ] Create first migration: `CREATE SCHEMA IF NOT EXISTS nexagent`
- [ ] Verify `alembic upgrade head` works against a fresh database
- [ ] Add migration commands to README / developer docs
- [ ] Add `alembic` to Dockerfile build if needed

**Acceptance Criteria:**
- `alembic upgrade head` creates the `nexagent` schema
- `alembic downgrade base` removes it cleanly
- Migrations are idempotent with existing shared DB tables in other schemas

---

### Epic 1.4: Base ORM Models
> Create the SQLAlchemy model base class and common patterns.

- [ ] Define `Base` in `models/base.py` with `__table_args__ = {"schema": "nexagent"}`
- [ ] Add common columns mixin or pattern for `id`, `created_at`, `updated_at`
- [ ] Create stub model files for all 6 entity tables (empty classes, correct imports)
- [ ] Verify all models register with `Base.metadata`
- [ ] Write a test that imports all models without error

**Acceptance Criteria:**
- `Base.metadata.tables` contains expected table references
- Models follow the naming convention from DATABASE.md
- No model defines columns yet (that's in later sprints) — only structure

---

### Epic 1.5: Dev Environment & Testing Infrastructure
> Make sure local development is smooth and repeatable.

- [ ] `docker-compose.dev.yml` includes PostgreSQL 16 + pgAdmin (optional)
- [ ] `.env.example` file with all required/optional env vars documented
- [ ] Pytest fixture for async DB session (test database, auto-rollback)
- [ ] `conftest.py` with session-scoped engine and function-scoped transactions
- [ ] Verify `pytest` runs clean with existing + new infra tests
- [ ] Add `Makefile` or `justfile` with common commands (`dev`, `test`, `migrate`, `lint`)

**Acceptance Criteria:**
- `docker compose -f docker-compose.dev.yml up` starts app + DB
- `pytest` passes with DB-dependent tests
- New developer can set up in < 5 minutes with documented steps
