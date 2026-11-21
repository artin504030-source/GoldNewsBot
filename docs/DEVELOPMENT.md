# GoldNewsBot development guide

## Branch and release safety

- Keep `main` deployable. Work on a short-lived feature, fix, or chore branch.
- Open a pull request into `main`; do not push experimental changes directly to the production branch.
- Review the diff and confirm the Python Tests workflow passes before merging.
- Keep credentials in GitHub Actions Secrets or environment variables. Never commit bot tokens, API keys, passwords, or personal user data.
- Grant each workflow only the GitHub token permissions it needs. Workflows that only read source should use `contents: read`.

## Local validation

Use Python 3.11 and install the pinned project requirements:

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python -m unittest discover -v
```

Run tests before opening a pull request. Do not run live Telegram delivery or dispatch production workflows as part of unit tests.

## Data and user safety

- Treat fetched news, RSS descriptions, and external content as untrusted input.
- Do not log Telegram tokens, API keys, or private user content.
- Keep news ingestion, AI analysis, Telegram delivery, and trading records as separate modules.
- Before introducing a persistent database, document its schema, backup/restore procedure, retention policy, and migration path from existing JSON files.
- Do not present model-generated analysis as verified fact or a guaranteed trading signal. Preserve source links, publication timestamps, uncertainty, and scenario assumptions.

## Current architecture baseline

The current project is a Python/Telegram news application with scheduled GitHub Actions workflows, JSON-backed history, market/news analysis modules, Telegram commands, and unit tests. User accounts, a persistent multi-user database, personal trade journal/P&L, and a conversational AI assistant are not yet implemented in this baseline. Update this section as architecture changes are merged.
