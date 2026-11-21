# GoldNewsBot — Infrastructure and Initial Build Plan

**Status:** Proposed rollout sequence  
**Principle:** Design first, parallel staging build second, production cutover only after acceptance checks.

## Phase A — Foundation and design (current phase)

- Freeze current behavior and capture baseline test/CI results.
- Document target architecture, module ownership, logical database schema, and data flows.
- Establish development/staging/production separation.
- Establish secrets, permissions, logging, backup, restore, and release policies.
- Keep current scheduled news workflows running until replacement paths are proven.

**Exit criteria:** architecture and data model reviewed; environment variables and secret inventory documented; staging plan approved; no production behavior changed.

## Phase B — Application foundation

1. Introduce configuration validation and typed settings.
2. Add PostgreSQL connection management and SQLAlchemy models.
3. Add Alembic migrations and migration smoke tests.
4. Add repository/service interfaces and dependency injection.
5. Add structured logging, correlation IDs, health/readiness endpoints.
6. Add integration-test database and isolated Telegram mock adapter.
7. Add CI stages for lint/type checks, unit tests, integration tests, migration checks, and dependency audit.

**Exit criteria:** app starts in local/staging without production secrets; migrations can upgrade a clean database; tests can run without sending Telegram messages.

## Phase C — Data migration and news core

1. Build JSON import/export commands.
2. Backup and checksum all legacy JSON state.
3. Import to staging and generate reconciliation report.
4. Implement news/source/translation/analysis repositories.
5. Run shadow comparisons with existing JSON behavior.
6. Switch one news read/write path at a time, with rollback.
7. Verify idempotent ingestion and duplicate-free notifications.

**Exit criteria:** counts and samples reconciled; source links and timestamps preserved; rollback demonstrated; production news delivery unchanged or demonstrably improved.

## Phase D — Product modules

Implement in this order:
1. Identity, access control, preferences, and user isolation.
2. AI provider gateway and structured news analysis.
3. Personal assistant conversation/command orchestration.
4. Trading accounts and manual journal with verified P&L.
5. Signal research engine with expiry, invalidation, and no execution capability.
6. Dashboard authentication and per-user analytics.

**Exit criteria:** feature-specific acceptance tests pass; all modules gated by feature flags; no cross-user data access.

## Phase E — Staging and production readiness

- Deploy a separate staging bot/token and database.
- Run scheduled jobs against staging or safe test feeds.
- Validate Telegram formatting, delivery retries, deduplication, and rate limits.
- Load-test source ingestion and dashboard read paths.
- Test DB backup/restore and application rollback.
- Review secrets, permissions, dependencies, data retention, and access controls.
- Prepare cutover checklist and incident rollback procedure.

**Exit criteria:** staging runs for an agreed observation period without data loss or duplicate delivery; all critical tests pass; restore test succeeds; no open critical/high security findings.

## Phase F — Controlled production rollout

1. Deploy schema migrations using backward-compatible changes.
2. Deploy application with new features disabled.
3. Enable read-only features for administrator.
4. Enable selected news features gradually.
5. Enable journal and AI after data isolation and cost controls pass.
6. Enable signal research only after strategy validation and clear disclaimers.
7. Monitor errors, latency, source health, notification delivery, and AI usage.
8. Roll back application or disable feature flags if acceptance thresholds fail.

## Decisions intentionally deferred

| Decision | Why deferred | Default recommendation |
|---|---|---|
| Hosting vendor | Need budget, region, uptime and operational preference | Managed Python worker/VPS with persistent storage |
| PostgreSQL provider | Must match host/network and backup policy | Managed PostgreSQL |
| AI provider/model | Need quality, cost, Persian/Dari performance and data policy comparison | Provider abstraction; no vendor lock-in |
| Public registration | Security and support requirements not yet implemented | Private allowlist first |
| Redis | No proven queue/load need yet | Defer; use DB outbox/job table initially |
| Broker integration | Increases security and financial risk | Exclude from initial release |
| Signal publication policy | Requires strategy rules and validation evidence | Private research-only mode first |

## Release gates

- [ ] CI green on exact release commit.
- [ ] Dependency audit reviewed; no unresolved critical/high vulnerabilities.
- [ ] Secret scanning or equivalent repository scan enabled.
- [ ] Staging secrets and production secrets are separate.
- [ ] Database migrations reviewed and tested.
- [ ] JSON migration reconciliation signed off.
- [ ] Backup and restore tested.
- [ ] Telegram identity and user isolation tests pass.
- [ ] News ingestion and notification idempotency tests pass.
- [ ] AI output schema/source attribution/cost limits tested.
- [ ] Journal P&L examples independently reconciled.
- [ ] Signals cannot submit broker orders.
- [ ] Monitoring, incident response, and rollback steps documented.
- [ ] Production cutover approved by repository owner.
