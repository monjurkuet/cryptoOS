# Whale Accuracy + Heatmap + Reliability Execution Plan

## Summary

This execution plan fixes the current dashboard data inaccuracies first, then adds liquidity heatmap and extended trader controls without increasing Hyperliquid WS client count or subscriptions per client. The implementation covers:

1. API/data-path reliability and timeout behavior.
2. Exact selected-whale data integrity across all views.
3. Trader analytics correctness (positions vs open orders).
4. New heatmap and market context endpoints using Binance public data.
5. UI expansion for full filter coverage and long/short side-by-side layout.
6. Binance Web3 leaderboard ingestion (separate source, clearly labeled).

## Implementation Changes

### 1) Reliability and health

- Dashboard server:
  - Enable Express trust-proxy for Caddy (`127.0.0.1`) to eliminate rate-limit proxy errors.
  - Refactor service client throttling to avoid hard `client busy` failures during concurrent whale queries.
  - Add structured stale/degraded response metadata to all whale and market routes.
- Market scraper:
  - Keep WS capacity fixed (`5 x 10`) and preserve rotation.
  - Tighten traders endpoint timeout and fallback behavior so request hangs do not propagate to dashboard.
  - Ensure selected-address requests are prioritized and include actionable status metadata per address.
- Relay/VPN:
  - Harden Binance relay DNS strategy:
    - try native DNS,
    - fallback to DoH (`cloudflare-dns.com` and `dns.google`),
    - cache resolved A records with TTL and health telemetry.
  - Expose relay DNS/upstream health in `/health`.

### 2) Whale data correctness

- Always resolve selected whale addresses via batch detail route, regardless of tab/toggle state.
- Selection mode precedence:
  - If user selected addresses, fetch and render exactly those addresses first.
  - Include status reason per address: active, flat, unknown, unavailable, upstream_error.
- Analytics pipeline:
  - Build sentiment, liquidity clusters, and trader analytics from selected detail payload when selection exists.
  - Fall back to general filtered trader list only when no selection is active.

### 3) Trader analytics model fixes

- Replace current open-order-as-position usage:
  - Position metrics come from normalized `positions`.
  - Order metrics come from normalized `open_orders`.
- Add derived fields in UI aggregation:
  - net exposure,
  - long/short notional,
  - avg entry by side,
  - avg leverage by side,
  - order-wall bias.

### 4) Filters and controls

- Expand whale filter UI to include all supported API filters:
  - score min/max,
  - account min/max,
  - tags any/all/exclude,
  - exact addresses,
  - has positions,
  - has open orders,
  - position status,
  - updated-within-hours,
  - profitable windows,
  - ROI day/week/month/all-time min/max,
  - volume day/week/month min/max,
  - sort by/dir,
  - pagination controls.
- Persist filter state to query params and local storage presets.

### 5) Whale positions tab layout changes

- Render long and short sections side-by-side in two columns:
  - Left: Long positions and long-side order clusters.
  - Right: Short positions and short-side order clusters.
- Keep shared summary row on top (consensus entry, net exposure, tracked cap, elite conviction).

### 6) Liquidity heatmap and market context

- Add server endpoints:
  - `/api/market/depth` (Binance futures depth snapshot),
  - `/api/market/liquidation-heatmap` (bucketed liquidation events + optional whale liquidation overlays),
  - `/api/market/futures-context` (open interest, top long/short ratio, taker buy/sell ratio).
- Use Binance public APIs and existing liquidation stream:
  - `/fapi/v1/depth`,
  - `/fapi/v1/openInterest`,
  - `/futures/data/topLongShortPositionRatio`,
  - `/futures/data/takerlongshortRatio`,
  - `!forceOrder@arr`.
- Add dashboard heatmap panel:
  - symbol selector,
  - bucket granularity,
  - timeframe,
  - source/degraded indicator.

### 7) Binance Web3 leaderboard integration

- Add separate route and UI source for `web3.binance.com` leaderboard:
  - fetch leaderboard pages by chain and period,
  - normalize and cache rows,
  - label source explicitly as Binance Web3 Leaderboard.
- Keep this data separate from Hyperliquid whale rows unless explicit address merge is requested.

## Test Plan

- Unit/integration:
  - service client concurrency/backoff path,
  - relay DNS fallback + health reporting,
  - selected-whale batch priority behavior,
  - trader analytics position/order aggregation,
  - heatmap endpoint schema and bucketing.
- End-to-end API:
  - whale traders and batch with selected addresses,
  - market depth/context/heatmap endpoints,
  - degraded/stale metadata responses.
- Dashboard verification:
  - selected whale list shows consistent data across overview + positions,
  - long/short columns render correctly,
  - expanded filters map to API params correctly,
  - heatmap and context panels render with live or degraded state.
- Production smoke checks:
  - `trading.datasolved.org` UI + API routes,
  - `trading-dashboard`, `market-scraper`, `binance-relay`, `signal-system` logs show no critical regressions.

## Assumptions

- Hyperliquid WS capacity remains unchanged (`5` clients, `10` subscriptions/client).
- If Binance upstream remains geo-restricted, relay will return degraded state and the dashboard must present it clearly instead of blank data.
- Web3 leaderboard data is additive and clearly source-labeled, not silently merged into Hyperliquid performance scores.
