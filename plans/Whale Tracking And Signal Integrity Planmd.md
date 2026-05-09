# Whale Tracking And Signal Integrity Plan

**Review Corrections**
- The audit is directionally right, but the first blocker is event flow: `trader_positions` and `scored_traders` are currently published `local_only`, so the separate signal-system can be starved of live data.
- Hyperliquid `webData2` is limited to 10 users per WS connection, so 500-1000 live WS traders cannot run through 1-2 clients. Use a variable tracked universe plus a prioritized live WS subset and HTTP polling for the rest.
- The dashboard repo confirms the 10-trader detail slice, 20-address proxy batch cap, unweighted sentiment, Binance liquidation context mismatch, and missing true whale watchlists.
- `liquidationPx` is already available from Hyperliquid position state; dashboard clusters should use that actual value instead of estimating.

**Backend Changes**
- Consolidate scored trader contracts: have market-scraper emit canonical `scored_traders` events with `address`, `score`, `account_value`, `tags`, `performances`, and `tracked_reason`; remove or fix the duplicate raw-leaderboard rescoring path.
- Restore Redis publication for compact `trader_positions` and `scored_traders` while keeping local dispatch for in-process storage/signal handlers.
- Change trader selection to include `score >= min_score OR account_value >= whale_threshold OR watchlist inclusion`, then cap by configurable `selection.max_count` default `500`, hard cap `1000`.
- Split tracking into `selected_traders`, `live_ws_traders`, and `polled_traders`: default live WS cap `200` via 20 clients, hard cap `300`; poll the remaining selected traders with 30s per-trader timeout, concurrency 5, and existing Hyperliquid rate limiting.
- Add trader batch/detail APIs: `POST /api/v1/traders/batch`, `GET /api/v1/traders?addresses=...`, and include normalized `liquidation_price`, `position_value`, `notional`, `open_orders`, and metrics.
- Add saved whale lists in MongoDB with `GET/POST/PUT/DELETE /api/v1/traders/watchlists`; watchlists are single-user/admin because current apps have no auth model.
- Add `GET /api/v1/traders/liquidity-clusters` using actual Hyperliquid `liquidationPx`, bucketed by price, returning long/short notional, trader count, missing-liquidation count, and source metadata.
- In signal-system, ingest scored trader metadata, wire `TraderWeightingEngine` into signal generation, and use leaderboard score as the available performance dimension instead of nonexistent sharpe/sortino fields.
- Add Redis subscriber health: last message time, per-channel counts, reconnect state, and payload lag exposed in health/stats endpoints.

**Dashboard Changes**
- Update `/api/whales/traders/batch` proxy to call the new backend batch endpoint directly and raise its cap to the backend limit instead of fanning out per address.
- Update `useWhaleDashboardData` to fetch all selected/top trader details, not `slice(0, 10)`, and key queries by the selected address list.
- Add a real whale selection UI: exact address paste/search, row checkboxes, select all filtered whales, saved-list dropdown, save/update/delete list actions.
- Change sentiment to notional-weighted voting: position absolute size times mark/entry price, optionally multiplied by account-value/score weight.
- Replace liquidation cluster formula with actual `liquidation_price`; skip/flag positions where Hyperliquid returns null.
- Keep Binance force-order feed only as explicitly labeled “Binance Futures Forced Liquidations”; add a separate “Hyperliquid Liquidation Levels” view from tracked whale positions.

**Tests**
- Market-scraper: selection includes low-ROI whales, batch API returns all requested traders, watchlist CRUD works, `liquidationPx` is preserved, and Redis publication is external when enabled.
- Signal-system: scored metadata ingestion stores account/score/tags, composite weights affect long/short bias, suppressed decisions remain visible, and Redis health reports stale/missing messages.
- Dashboard: unit tests for weighted sentiment and actual-liq clusters; integration tests for batch route, watchlist flow, and no 10-trader truncation.
- Verification commands: market-scraper pytest for trader/leaderboard/ws/signal tests, signal-system pytest for event/processor/weighting tests, dashboard `npm run lint` and `npm run build`.

**Assumptions**
- “30 seconds per trader” means per-trader HTTP timeout, not guaranteed 30s freshness for all 1000 traders; 1000 traders require at least about 2000 Hyperliquid HTTP requests per full poll cycle.
- Default deployment remains budget-aware: 500 selected traders, 200 live WS traders, and the rest polled. Increase only after health metrics show memory and event-loop headroom.
- Binance data is not mixed into Hyperliquid whale analytics unless the UI labels the exchange/source clearly.
