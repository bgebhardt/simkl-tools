# simkl-tools — project context for Claude/Hermes

## What this is

A local-first Python CLI and library for Bryan (Kermit) to interact with his SIMKL watchlists via the SIMKL API. The goal is to let Hermes/Kermit inspect lists, suggest next watches, and eventually write back (add/move/mark watched).

## Package layout

```
src/simkl_tools/
  __init__.py      # version export
  __main__.py      # python -m simkl_tools entry
  config.py        # Config dataclass, load_config() from env vars
  client.py        # SimklClient — all HTTP; uses stdlib urllib only
  cli.py           # argparse CLI: config-check, list, move, mark-watched
tests/
  test_client.py   # unit tests: request construction, validation, dry-run
  test_cli.py      # CLI integration tests (all offline, no network)
```

## Key design decisions

- **stdlib urllib only** for HTTP — no `requests` to keep deps minimal.
- **Dry-run by default** for all write operations. `--execute` is required to send. This matches the safety model for a personal tool that modifies remote state.
- **Env vars only** for credentials — never written to files.
- `src/` layout with `hatchling` build backend.

## SIMKL API facts

- Base URL: `https://api.simkl.com`
- Every request needs query params: `client_id`, `app-name`, `app-version`
- Authenticated requests need: `Authorization: Bearer ACCESS_TOKEN`
- Read list: `GET /sync/all-items/{type}/{status}` — types: movies/shows/anime; statuses: watching/plantowatch/hold/completed/dropped
- Move to list: `POST /sync/add-to-list` — body: `{"list": "<status>", "movies": [...], "shows": [...], "anime": [...]}`
- Mark watched: `POST /sync/history` — preferred for completed writes; body same shape without `list`

## Common commands

```sh
# Install + run tests
uv sync --dev
uv run pytest -v

# Check config
simkl-tools config-check

# Read
simkl-tools list --type shows --status watching
simkl-tools list --type movies --status plantowatch

# Dry-run write (safe)
simkl-tools move completed '[{"ids":{"simkl":12345},"type":"shows"}]'
simkl-tools mark-watched '[{"ids":{"simkl":67890},"type":"movies"}]'

# Actually execute
simkl-tools move completed '[...]' --execute
simkl-tools mark-watched '[...]' --execute
```

## Near-term additions

- `simkl-tools auth` — OAuth PIN/device-code flow helper to get an access token
- `simkl-tools suggest` — Hermes picks next watch from plan-to-watch
- Local cache with `date_from` incremental sync
