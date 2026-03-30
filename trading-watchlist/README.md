# trading-watchlist

Stateless FastAPI service that exposes trading watchlist data through a repository layer. `state.json` in `/mnt/vhd/trading/data/` is now the preferred canonical structured source when present, with markdown parsing kept as fallback.

## Run

```bash
uv sync
uv run uvicorn trading_watchlist.api.main:app --reload --port 3846
```

## Quick check

```bash
uv run python -c "from trading_watchlist.api.main import create_app; app=create_app(); print(app.title)"
```

## Structured mode

- Default markdown inputs remain: `/mnt/vhd/trading/analysis-rules.md`, `/mnt/vhd/trading/analysis-trades.md`, `/mnt/vhd/trading/analysis-watchlist.md`
- Generated scaffold markdown outputs live alongside those inputs: `analysis-rules.generated.md`, `analysis-trades.generated.md`, `analysis-watchlist.generated.md`, `analysis-brief.generated.md`
- Structured JSON inputs are read from `/mnt/vhd/trading/data/` by default: `rules.json`, `positions.json`, `watchlist.json`, `prices.json`, `state.json`, `manifest.json`
- The API treats `state.json` as canonical when it exists. `get_rules`, `get_positions`, `get_watchlist`, `get_prices`, and `get_state` all derive from `state.json` first.
- If `state.json` is absent, split JSON files still work as fallback structured inputs. Missing structured files still fall back to markdown for that document.
- `GET /api/v1/prices` uses canonical state first when available; otherwise it uses `prices.json` or aggregates from the active rules, positions, and watchlist sources. BTC still prefers the configured market API when available.
- `state.json` is the canonical bundled structured state document for integrations and future persistence work. It includes `schema_version`, `generated_at`, `prices`, `rules`, `positions`, `watchlist`, and lightweight source metadata.
- `manifest.json` is a lightweight export manifest that lists the generated file names, timestamps, and source mode.
- Current write paths are:
  - `markdown inputs -> StateBundle -> writer -> state.json + split JSON artifacts + generated markdown scaffolds`
  - `external StateBundle -> API/CLI -> writer -> state.json + split JSON artifacts + generated markdown scaffolds`
- Current refresh path from canonical state is `state.json -> refresh CLI -> split JSON artifacts + generated markdown scaffolds`
- Canonical file for machine consumption is `state.json`. Split JSON files and `.generated.md` files are derived artifacts.
- Generated `.generated.md` files are scaffold outputs derived from canonical state and are safe to overwrite.
- Human-maintained `analysis-*.md` files remain the markdown fallback source during this phase.
- Recommended integration path: prefer `GET /api/v1/state` or `state.json` instead of stitching together multiple split files.

Recommended future flow:

- External system produces a validated `StateBundle`
- Write it directly with `PUT /api/v1/state` or `trading-watchlist-write-state`
- `state.json` remains canonical
- `manifest.json`, split JSON files, and `.generated.md` scaffolds are regenerated automatically

Override the JSON directory with `TRADING_WATCHLIST_STRUCTURED_DATA_DIR`.

## Seed canonical state from markdown

```bash
uv run trading-watchlist-seed-json
```

This seed workflow writes all structured artifacts in one pass:

- `rules.json`
- `positions.json`
- `watchlist.json`
- `prices.json`
- `state.json`
- `manifest.json`
- `analysis-rules.generated.md`
- `analysis-trades.generated.md`
- `analysis-watchlist.generated.md`
- `analysis-brief.generated.md`

Optional custom paths:

```bash
uv run trading-watchlist-seed-json --trading-data-dir /mnt/vhd/trading --structured-data-dir /mnt/vhd/trading/data --generated-markdown-dir /mnt/vhd/trading
```

## Refresh derived artifacts from canonical state

```bash
uv run trading-watchlist-refresh-from-state
```

This path reads `state.json` and rewrites:

- `rules.json`
- `positions.json`
- `watchlist.json`
- `prices.json`
- `manifest.json`
- `analysis-rules.generated.md`
- `analysis-trades.generated.md`
- `analysis-watchlist.generated.md`
- `analysis-brief.generated.md`

Optional custom paths:

```bash
uv run trading-watchlist-refresh-from-state --structured-data-dir /mnt/vhd/trading/data --generated-markdown-dir /mnt/vhd/trading
```

This refresh does not touch the human-authored `analysis-rules.md`, `analysis-trades.md`, or `analysis-watchlist.md` files.

## Write canonical state directly

For local integrations, write a full `StateBundle` directly instead of going through markdown parsing.

API:

```bash
curl -X PUT "http://127.0.0.1:3846/api/v1/state" \
  -H "Content-Type: application/json" \
  --data-binary @/path/to/state.json
```

CLI:

```bash
uv run trading-watchlist-write-state --input /path/to/state.json
```

Optional custom paths:

```bash
uv run trading-watchlist-write-state --input /path/to/state.json --structured-data-dir /mnt/vhd/trading/data --generated-markdown-dir /mnt/vhd/trading
```

This direct-write path persists:

- `state.json`
- `manifest.json`
- `rules.json`
- `positions.json`
- `watchlist.json`
- `prices.json`
- `analysis-rules.generated.md`
- `analysis-trades.generated.md`
- `analysis-watchlist.generated.md`
- `analysis-brief.generated.md`

Only `.generated.md` scaffold files are overwritten. Human-authored `analysis-*.md` files are left untouched.

## API examples

```bash
curl "http://127.0.0.1:3846/api/v1/prices"
curl "http://127.0.0.1:3846/api/v1/state"
curl -X PUT "http://127.0.0.1:3846/api/v1/state" -H "Content-Type: application/json" --data-binary @/path/to/state.json
curl "http://127.0.0.1:3846/api/v1/rules?asset=BTC&status=TRIGGERED&direction=SHORT"
curl "http://127.0.0.1:3846/api/v1/positions?asset=BTC&section=Open%20Positions&direction=SHORT"
curl "http://127.0.0.1:3846/api/v1/approaching?asset=BTC&rule_id=CC-20260326-BTC-03"
curl "http://127.0.0.1:3846/api/v1/alerts?asset=BTC&priority=CRITICAL"
```

`GET /api/v1/prices` returns normalized prices plus lightweight `sources` metadata. BTC prefers the configured market API, while the remaining assets come from either structured JSON or markdown fallback.

`GET /api/v1/state` returns the canonical bundled state for integrations. Existing split endpoints remain available for narrow reads and backwards compatibility.

## Test

```bash
uv run pytest
```
