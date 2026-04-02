# S7 — Security & Production Readiness

> **Milestone:** Production-ready, hardened, deployable  
> **Goal:** Secure API key handling, authentication, rate limiting, and deployment hardening for production use.  
> **Depends on:** S6 (Timeline & Observability)

---

## Epics

### Epic 7.1: Authentication & Authorization Middleware
> Protect all API endpoints with JWT-based authentication.

- [ ] Add `AUTH_ENABLED` toggle to config (default: `false` for dev, `true` for prod)
- [ ] JWT validation middleware — verify tokens from the shared microservice auth system
- [ ] `AUTH_JWT_SECRET` or `AUTH_JWKS_URL` config for token verification
- [ ] Public endpoints: `/health`, `/docs` (OpenAPI)
- [ ] Protected endpoints: everything else requires valid Bearer token
- [ ] Extract user identity from token (for future multi-tenancy)
- [ ] Tests with auth enabled and disabled

**Acceptance Criteria:**
- All protected endpoints return 401 without valid token
- Valid tokens grant access
- `/health` and `/docs` remain publicly accessible
- Auth can be disabled for local development

---

### Epic 7.2: API Key Security Hardening
> Ensure all stored API keys are handled securely end-to-end.

- [ ] Audit all code paths where `api_key_encrypted` is read/written
- [ ] Verify API keys never appear in logs (mask in any log output)
- [ ] Verify API keys never appear in API responses (already covered in schemas)
- [ ] Verify API keys never appear in execution step `input_data`/`output_data`
- [ ] Key rotation support: re-encrypt all keys when `ENCRYPTION_KEY` changes
- [ ] `POST /api/v1/admin/rotate-encryption` endpoint (admin-only)
- [ ] Tests: key masking in logs, response sanitization

**Acceptance Criteria:**
- No code path leaks plaintext API keys
- Key rotation works without downtime
- Audit trail for key access (future: logging)

---

### Epic 7.3: Input Validation & Sanitization
> Harden all API inputs against injection and abuse.

- [ ] Review all Pydantic schemas for proper constraints (max lengths, patterns, enums)
- [ ] JSONB fields (`input_schema`, `config`, `graph_layout`): max depth/size limits
- [ ] Task input: reasonable max length, no script injection concerns (LLM input, not rendered)
- [ ] Tool `api_call` config: validate URLs, disallow private/internal IPs (SSRF prevention)
- [ ] Rate limiting on execution endpoints (configurable per-minute limit)
- [ ] Tests for boundary cases and malicious inputs

**Acceptance Criteria:**
- Oversized payloads rejected with 422
- Private IP URLs in tool configs rejected
- Rate limiting returns 429 when exceeded
- All validation errors return structured error responses

---

### Epic 7.4: Error Handling & Resilience
> Consistent error handling across the application.

- [ ] Global exception handler in FastAPI — structured error responses
- [ ] LLM provider errors (rate limits, timeouts, auth failures) caught and surfaced clearly
- [ ] Sub-agent failures isolated — one failure doesn't crash the execution
- [ ] Database connection retry logic
- [ ] Graceful shutdown: in-progress executions marked as `failed` on shutdown
- [ ] Health endpoint checks: DB, optional LLM ping

**Acceptance Criteria:**
- No unhandled exceptions in production
- All errors return `{detail: str, error_code: str}` structure
- Partial execution failures preserve completed results
- App shutdown marks running executions as interrupted

---

### Epic 7.5: Deployment & Docker Hardening
> Production-ready container and deployment configuration.

- [ ] Non-root user in Dockerfile
- [ ] Read-only filesystem where possible
- [ ] Resource limits in docker-compose-dokploy.yml (memory, CPU)
- [ ] Alembic migrations run on startup (or via init container)
- [ ] Environment-specific compose overrides
- [ ] Secrets management: verify no secrets in image layers
- [ ] Health check aligned with new DB-aware health endpoint
- [ ] Update README with production deployment guide

**Acceptance Criteria:**
- Container runs as non-root
- Migrations apply cleanly on fresh and existing deployments
- No secrets baked into the Docker image
- Health check reflects full system readiness

---

### Epic 7.6: Observability & Logging
> Structured logging and monitoring hooks for production.

- [ ] Structured JSON logging (replace print statements if any)
- [ ] Request ID middleware — trace a request across all log lines
- [ ] Log execution lifecycle events (start, delegation, completion, failure)
- [ ] LangSmith integration: ensure tracing works for all LLM calls (master + sub-agents)
- [ ] Optional: Prometheus metrics endpoint (`/metrics`) for request counts, latencies, execution stats
- [ ] Log level configurable via `LOG_LEVEL` env var

**Acceptance Criteria:**
- All logs are structured JSON with timestamp, level, request_id
- Execution events traceable end-to-end
- LangSmith receives traces from all LLM invocations
- Log level adjustable without code changes

---

### Epic 7.7: Documentation & API Reference
> Complete documentation for developers and operators.

- [ ] Update README.md: new architecture, endpoints, configuration
- [ ] API reference auto-generated from OpenAPI (FastAPI `/docs` already does this)
- [ ] Environment variable reference table (all settings with defaults and descriptions)
- [ ] Deployment guide: Dokploy, Docker, local dev
- [ ] Developer guide: adding new tools, creating sub-agents, running executions
- [ ] Example workflows (curl commands or Postman collection)

**Acceptance Criteria:**
- New developer can understand and deploy the system from docs alone
- All env vars documented
- Example API calls for every major operation
- Architecture diagrams up to date with implementation
