# GoldNewsBot — Initial Data Model

**Status:** Logical schema proposal; no production tables created yet.  
**Database recommendation:** PostgreSQL. Use UUID primary keys, UTC timestamps, foreign keys, indexes, migrations, and decimal/numeric types for prices and money.

## 1. Data ownership and tenancy

Every private record belongs to a user or an account/workspace. Shared public news records are global; user-specific notes, watchlists, trades, settings, and notifications are private. Authorization must be checked in application services and enforced with database constraints/row-level security where practical.

## 2. Core entities

| Table | Key fields | Purpose |
|---|---|---|
| `users` | id, telegram_user_id, username, display_name, timezone, status, created_at | Identity linked to Telegram |
| `roles` | id, name | admin, operator, user |
| `user_roles` | user_id, role_id | Role membership |
| `user_preferences` | user_id, language, timezone, notification_settings, risk_preferences | User-specific settings |
| `news_sources` | id, name, source_type, base_url, language, enabled, health_status | Feed/source registry |
| `news_items` | id, source_id, external_id, canonical_url, title, body, language, published_at, fetched_at, fingerprint, status | Canonical news archive |
| `news_translations` | id, news_item_id, target_language, translated_title, translated_body, provider, created_at | Translation versions |
| `news_tags` | id, slug, label | Topic taxonomy |
| `news_item_tags` | news_item_id, tag_id | News/topic relation |
| `analysis_runs` | id, news_item_id, analysis_type, provider, model, prompt_version, result_json, confidence, created_at | Rule/AI analysis history |
| `market_instruments` | id, symbol, asset_class, quote_currency, contract_spec_json, enabled | Instrument metadata |
| `market_observations` | id, instrument_id, observed_at, price, source, metadata_json | Optional historical context |
| `watchlists` | id, user_id, name | User watchlists |
| `watchlist_items` | watchlist_id, instrument_id | Watchlist members |
| `trading_accounts` | id, user_id, name, currency, starting_balance, account_type, status | User-defined journal accounts |
| `trades` | id, user_id, account_id, instrument_id, side, status, opened_at, closed_at, notes | Trade aggregate |
| `trade_events` | id, trade_id, event_type, event_at, quantity, price, fee, currency, metadata_json | Immutable fills/partial closes/adjustments |
| `trade_metrics` | id, trade_id, realized_pnl, risk_amount, r_multiple, calculation_version, calculated_at | Derived, reproducible metrics |
| `strategy_definitions` | id, owner_user_id, name, version, rules_json, enabled | Strategy configurations |
| `signal_setups` | id, strategy_id, instrument_id, timeframe, direction, entry_json, stop_price, targets_json, rationale, status, expires_at | Research setup lifecycle |
| `signal_events` | id, signal_setup_id, event_type, event_at, details_json | Published, invalidated, expired, target/stop outcome |
| `notification_outbox` | id, user_id, event_type, payload_json, idempotency_key, status, attempts, next_attempt_at, sent_at | Reliable delivery queue |
| `notification_deliveries` | id, outbox_id, channel, external_message_id, status, error_code, delivered_at | Delivery audit |
| `conversation_sessions` | id, user_id, channel, state_json, updated_at | Short-lived assistant context |
| `conversation_messages` | id, session_id, role, content, created_at, metadata_json | Conversation history, subject to retention |
| `audit_events` | id, actor_user_id, action, entity_type, entity_id, occurred_at, metadata_json | Security and admin audit |
| `system_jobs` | id, job_type, dedupe_key, status, attempts, scheduled_at, started_at, finished_at, last_error | Job execution state |
| `schema_migrations` | managed by Alembic | Database schema version |

## 3. Important constraints and indexes

- Unique `users.telegram_user_id` when present.
- Unique `news_items(source_id, external_id)` when external ID exists.
- Unique `news_items.canonical_url` where canonical URL is present; use fingerprint as secondary dedupe key.
- Unique `notification_outbox.idempotency_key`.
- Index news by `published_at`, `source_id`, and status.
- Index analysis by `news_item_id, created_at`.
- Index trades by `user_id, account_id, opened_at`.
- Index trade events by `trade_id, event_at`.
- Index signals by `instrument_id, status, expires_at`.
- Use `NUMERIC` for prices, quantities, fees, balances, and P&L; never binary floating point for money.
- Use `TIMESTAMPTZ` and store UTC.
- Use JSONB only for provider-specific metadata or versioned flexible payloads; keep query-critical fields relational.
- Apply foreign keys and deliberate delete behavior. Prefer soft-deactivation for users and sources where audit history must remain.

## 4. Trade accounting policy

A trade is an aggregate; fills and partial closes are immutable events. Do not overwrite history to represent a partial close. The first journal release must explicitly choose and document:
- Position sizing and contract multiplier per instrument.
- Quote/base currency conversion source and timestamp.
- Fee, commission, swap/funding, and spread treatment.
- Realized P&L formula for long and short trades.
- Whether the account uses FIFO, average cost, or another matching method.
- Treatment of partial close, scale-in, scale-out, and corrections.
- R-multiple calculation and initial risk definition.

No P&L dashboard should be labeled accurate until these rules are implemented and tested against manually verified examples.

## 5. News migration mapping

| Existing JSON/state | Target table |
|---|---|
| `news_archive.json` | `news_items`, `news_sources`, `news_item_tags` |
| `seen_news.json` | dedupe keys and canonical `news_items` |
| `source_health.json` | `news_sources` health fields + source-health events |
| `health_state.json`, `health_alert_state.json` | `system_jobs` / health state |
| `telegram_update_offset.json` | Telegram adapter cursor/state table |
| `analysis` outputs | `analysis_runs` |
| Future personal trade records | `trading_accounts`, `trades`, `trade_events`, `trade_metrics` |

## 6. Migration safety plan

1. Freeze and checksum source JSON files; store a timestamped backup outside the Git repository.
2. Build a read-only importer and schema validation report.
3. Import into a disposable staging database; retain original source file and row-level error report.
4. Reconcile counts, duplicate keys, missing IDs, timestamps, source attribution, and representative samples.
5. Run the old JSON reader and staging DB reader in shadow mode; compare outputs.
6. Enable database reads for a small controlled path; keep rollback to JSON snapshot available.
7. Only after stable operation, switch writes to database. Avoid uncoordinated dual-write; use an outbox or a single authoritative writer.
8. Retain export and restore tooling; delete legacy JSON only after an explicit retention decision and verified backups.

## 7. Privacy and retention decisions required before public access

- Define whether conversation messages are stored and for how long.
- Define user export and deletion behavior.
- Define retention for trade journal and audit records.
- Restrict admins from viewing private trade notes unless explicitly authorized.
- Avoid storing broker passwords, API trading credentials, or unnecessary identity data.
- Define whether news content is stored as full text or only metadata/excerpts, considering source terms.
