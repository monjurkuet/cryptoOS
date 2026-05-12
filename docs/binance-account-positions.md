# Binance Saved Account Positions

`market-scraper` can serve a small `/account` page where users create a local account, save Binance.com read-only API credentials, and view live spot balances plus USD-M futures positions.

## Configuration

MongoDB is required because local users, sessions, and encrypted Binance connections are persisted in `market_scraper`.

```env
MONGO__URL=mongodb://localhost:27017
MONGO__DATABASE=market_scraper
BINANCE_ACCOUNT__ENABLED=true
BINANCE_CREDENTIAL_ENCRYPTION_KEY=<fernet-key>
BINANCE_ACCOUNT__SPOT_BASE_URL=https://api.binance.com
BINANCE_ACCOUNT__FUTURES_BASE_URL=https://fapi.binance.com
AUTH__SESSION_COOKIE_SECURE=false
```

Generate a Fernet key:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `AUTH__SESSION_COOKIE_SECURE=true` when serving over HTTPS.

## Security Model

- Users create local email/password accounts; passwords are hashed with Argon2id.
- Session cookies are `HttpOnly` and `SameSite=Lax`.
- Authenticated write routes require an `X-CSRF-Token` header.
- Binance API keys and secrets are encrypted with `BINANCE_CREDENTIAL_ENCRYPTION_KEY`.
- API responses expose only masked Binance API-key metadata.
- The Binance client uses only signed read-only account endpoints; it does not implement trading, order, transfer, or withdrawal calls.

## API

Auth:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

Binance connections:

- `POST /api/v1/binance/connections`
- `GET /api/v1/binance/connections`
- `DELETE /api/v1/binance/connections/{connection_id}`
- `GET /api/v1/binance/positions?connection_id=...&include_zero=false`

`GET /api/v1/binance/positions` returns:

- `totals`: estimated USDT value, spot value, futures wallet balance, futures unrealized PnL.
- `spot_balances`: asset, free, locked, total, USDT price, USDT value.
- `futures_positions`: symbol, side, amount, entry, mark, notional, unrealized PnL, leverage, margin type, liquidation price.
- `warnings`: timestamp-drift retry, missing spot valuation pairs, or other recoverable conditions.

## Binance Setup

Create a Binance.com API key with read-only permissions. Do not grant trading or withdrawal permissions. The implementation targets Binance.com base URLs by default, not Binance.US.
