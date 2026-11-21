# Development

## Safe integration stages
- Stage B: read-only foundation preflight.
- Stage C: legacy RSS dry-run adapter (no send and no state writes).
- Stage D: isolated Persian Telegram news-post formatter (no send, fetch, translation, or state writes).

See INTEGRATION_STAGE_B.md, INTEGRATION_STAGE_C.md, and INTEGRATION_STAGE_D.md for scope and validation details.

All integration work is developed on integrate/foundation-preflight. Do not merge into main or enable production delivery until the staged tests and user review are complete.
