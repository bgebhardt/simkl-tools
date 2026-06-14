# simkl-tools

Local CLI and Python library for inspecting and managing Bryan's [SIMKL](https://simkl.com) watchlists via the [SIMKL API](https://api.simkl.org/).

---

## Features

- Read watchlists (`movies`, `shows`, `anime`) filtered by status
- Dry-run-safe writes: move items between statuses, mark items watched
- Pure stdlib HTTP — no `requests`, no heavy deps
- Config from env vars only — no credentials ever touch a file

---

## Setup

### 1. Clone and install

```sh
git clone <repo>
cd simkl-tools
uv sync --dev          # installs package + pytest in .venv
```

Or with pip:

```sh
pip install -e .
```

### 2. Create a SIMKL developer app

1. Go to <https://simkl.com/settings/developer/> and create a new app.
2. Note your **Client ID**.
3. Use the OAuth flow (or the SIMKL API sandbox) to obtain an **Access Token** with the `public` and `sync` scopes. For personal local use, the PIN/device-code flow is simplest:
   ```
   GET https://api.simkl.com/oauth/pin?client_id=YOUR_CLIENT_ID
   # follow the user_code URL in a browser, approve, then:
   GET https://api.simkl.com/oauth/pin/DEVICE_CODE?client_id=YOUR_CLIENT_ID
   # repeat until "result": "approved" — the response contains your access_token
   ```

### 3. Set environment variables

Copy `.env.example` to `.env` and fill in your values, then `source .env` (or use `direnv`):

```sh
cp .env.example .env
$EDITOR .env
source .env
```

---

## Environment variables

| Variable              | Required | Default        | Description                          |
| --------------------- | -------- | -------------- | ------------------------------------ |
| `SIMKL_CLIENT_ID`     | yes      | —              | Your SIMKL developer app client ID   |
| `SIMKL_ACCESS_TOKEN`  | for writes/reads | —    | OAuth bearer token (personal account) |
| `SIMKL_APP_NAME`      | no       | `simkl-tools`  | Sent as `app-name` query param       |
| `SIMKL_APP_VERSION`   | no       | `0.1.0`        | Sent as `app-version` query param    |

---

## CLI usage

```
simkl-tools <subcommand> [options]
```

### `config-check`

Verify that env vars are configured correctly before making any API calls.

```sh
simkl-tools config-check
```

### `list`

Fetch items from your watchlist.

```sh
# shows currently watching (default)
simkl-tools list

# movies you plan to watch
simkl-tools list --type movies --status plantowatch

# anime updated since a date
simkl-tools list --type anime --status watching --date-from 2024-01-01T00:00:00Z
```

Options: `--type {anime,movies,shows}`, `--status {completed,dropped,hold,plantowatch,watching}`, `--date-from YYYY-MM-DDTHH:MM:SSZ`, `--extended full`

### `add-to-list`

Move one or more items to a different watchlist status. **Dry-run by default.**

```sh
# Preview what would be sent:
simkl-tools add-to-list plantowatch '[{"ids":{"simkl":12345},"type":"shows"}]'

# Or read the item payload from a file:
simkl-tools add-to-list plantowatch --item-json ./item.json

# Actually send:
simkl-tools add-to-list plantowatch --item-json ./item.json --execute
```

Alias: `move`.

### `add-history`

Add items to your watch history via `POST /sync/history`. **Dry-run by default.**

```sh
# Preview:
simkl-tools add-history '[{"ids":{"simkl":12345},"type":"movies","watched_at":"2024-06-01T20:00:00Z"}]'

# Actually send:
simkl-tools add-history --item-json ./watched.json --execute
```

Alias: `mark-watched`.

---

## Python library usage

```python
from simkl_tools.config import load_config
from simkl_tools.client import SimklClient

cfg = load_config(require_token=True)
client = SimklClient(cfg)

# Read your plan-to-watch shows
items = client.all_items("shows", "plantowatch")

# Dry-run a list move (no network call)
preview = client.add_to_list(
    [{"ids": {"simkl": 12345}, "type": "shows"}],
    target_status="watching",
    dry_run=True,
)

# Actually mark a movie watched
client.add_to_history(
    [{"ids": {"simkl": 67890}, "type": "movies"}],
    dry_run=False,
)
```

---

## Safety model

All write operations (`move`, `mark-watched`) default to **dry-run mode**.  
In dry-run mode:
- No network request is made.
- The planned HTTP method, URL, and request body are printed as JSON so you can review exactly what would be sent.
- Pass `--execute` on the CLI (or `dry_run=False` in the library) to actually send.

Credentials are read exclusively from environment variables and are never written to files by this tool.

---

## Running tests

```sh
uv run pytest -v
```

All tests are offline (no network calls). Secrets are never referenced in tests.

---

## Related work

These projects were used as API surface references during development. No code was copied.

- [simkl-mcp](https://github.com/srevinsaju/simkl-mcp) — MIT, TypeScript, Cloudflare Workers MCP server; good reference for SIMKL OAuth and sync endpoints
- [simkl-http-client](https://github.com/dvcol/simkl-http-client) — MIT, TypeScript HTTP client; comprehensive type definitions for SIMKL API responses
- [simkl-client](https://github.com/srgsf/simkl-client) — Java wrapper; older but covers the core sync API

---

## Next steps

- OAuth PIN/device-code helper command (`simkl-tools auth`)
- `suggest` subcommand — Hermes/Kermit picks next watch from plan-to-watch list based on genre/mood
- Richer output formatting (table, compact) via `--format`
- Cache layer: store list locally and only fetch changed items via `date_from`
- GitHub Actions CI
