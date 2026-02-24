#!/usr/bin/env python3
"""Price accuracy monitor script.

Monitors BTC price from our API vs Hyperliquid direct API
and reports accuracy statistics.
"""

import asyncio
import json
import time
from datetime import UTC, datetime

import httpx


# Configuration
OUR_API_URL = "http://localhost:8000"
HYPERLIQUID_API = "https://api.hyperliquid.xyz"
MONITOR_DURATION_SECONDS = 120  # 2 minutes
POLL_INTERVAL_SECONDS = 10  # Check every 10 seconds


async def get_our_price(client: httpx.AsyncClient) -> dict:
    """Get BTC price from our API."""
    try:
        response = await client.get(f"{OUR_API_URL}/api/v1/markets/BTC", timeout=5.0)
        response.raise_for_status()
        data = response.json()
        candle = data.get("latest_candle", {})
        return {
            "price": candle.get("c"),
            "high": candle.get("h"),
            "low": candle.get("l"),
            "open": candle.get("o"),
            "volume": candle.get("v"),
            "timestamp": candle.get("t"),
        }
    except Exception as e:
        return {"error": str(e)}


async def get_hyperliquid_price(client: httpx.AsyncClient) -> dict:
    """Get BTC price directly from Hyperliquid."""
    try:
        response = await client.post(
            f"{HYPERLIQUID_API}/info",
            json={"type": "allMids"},
            timeout=5.0,
        )
        response.raise_for_status()
        data = response.json()
        btc_price = float(data.get("BTC", 0))
        return {"price": btc_price}
    except Exception as e:
        return {"error": str(e)}


async def get_historical_candles(client: httpx.AsyncClient, timeframe: str, limit: int = 5) -> dict:
    """Get historical candles from our API."""
    try:
        response = await client.get(
            f"{OUR_API_URL}/api/v1/markets/BTC/history",
            params={"timeframe": timeframe, "limit": limit},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def calculate_accuracy(our_price: float, hl_price: float) -> dict:
    """Calculate accuracy metrics."""
    if our_price is None or hl_price is None:
        return {"error": "Missing price data"}

    diff = abs(our_price - hl_price)
    diff_pct = (diff / hl_price) * 100

    return {
        "difference_usd": round(diff, 2),
        "difference_pct": round(diff_pct, 4),
        "accurate": diff_pct < 1.0,  # Consider accurate if < 1% difference
    }


async def run_monitor():
    """Run the price monitoring loop."""
    print("=" * 70)
    print("BTC PRICE ACCURACY MONITOR")
    print("=" * 70)
    print(f"Duration: {MONITOR_DURATION_SECONDS}s | Interval: {POLL_INTERVAL_SECONDS}s")
    print(f"Our API: {OUR_API_URL}")
    print(f"Hyperliquid API: {HYPERLIQUID_API}")
    print("=" * 70)
    print()

    results = []
    iterations = MONITOR_DURATION_SECONDS // POLL_INTERVAL_SECONDS

    async with httpx.AsyncClient() as client:
        for i in range(iterations):
            iteration = i + 1
            timestamp = datetime.now(UTC).strftime("%H:%M:%S")

            print(f"[{timestamp}] Iteration {iteration}/{iterations}")
            print("-" * 50)

            # Fetch both prices in parallel
            our_task = get_our_price(client)
            hl_task = get_hyperliquid_price(client)
            our_data, hl_data = await asyncio.gather(our_task, hl_task)

            our_price = our_data.get("price")
            hl_price = hl_data.get("price")

            # Check for errors
            if "error" in our_data:
                print(f"  ❌ Our API Error: {our_data['error']}")
            if "error" in hl_data:
                print(f"  ❌ Hyperliquid Error: {hl_data['error']}")

            if our_price and hl_price:
                accuracy = calculate_accuracy(our_price, hl_price)

                print(f"  Our API (candle close): ${our_price:,.2f}")
                print(f"  Hyperliquid (mid):      ${hl_price:,.2f}")
                print(f"  Difference:             ${accuracy['difference_usd']:,.2f} ({accuracy['difference_pct']:.4f}%)")

                if accuracy["accurate"]:
                    print(f"  Status: ✅ ACCURATE")
                else:
                    print(f"  Status: ⚠️  DEVIATION DETECTED")

                results.append({
                    "timestamp": timestamp,
                    "our_price": our_price,
                    "hl_price": hl_price,
                    "accuracy": accuracy,
                })

                # Show candle details
                if our_data.get("high"):
                    print(f"\n  Candle Details:")
                    print(f"    Open:   ${our_data.get('open'):,.2f}")
                    print(f"    High:   ${our_data.get('high'):,.2f}")
                    print(f"    Low:    ${our_data.get('low'):,.2f}")
                    print(f"    Close:  ${our_price:,.2f}")
                    print(f"    Volume: {our_data.get('volume'):,.2f} BTC")

            print()

            # Wait for next iteration
            if i < iterations - 1:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

    # Print summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if results:
        our_prices = [r["our_price"] for r in results]
        hl_prices = [r["hl_price"] for r in results]
        diffs = [r["accuracy"]["difference_pct"] for r in results]

        print(f"Total Samples:      {len(results)}")
        print(f"Our Avg Price:      ${sum(our_prices)/len(our_prices):,.2f}")
        print(f"HL Avg Price:       ${sum(hl_prices)/len(hl_prices):,.2f}")
        print(f"Max Difference:     {max(diffs):.4f}%")
        print(f"Min Difference:     {min(diffs):.4f}%")
        print(f"Avg Difference:     {sum(diffs)/len(diffs):.4f}%")

        accurate_count = sum(1 for r in results if r["accuracy"]["accurate"])
        accuracy_rate = (accurate_count / len(results)) * 100
        print(f"Accuracy Rate:      {accuracy_rate:.1f}% ({accurate_count}/{len(results)})")

        # Final verdict
        print()
        if accuracy_rate >= 95:
            print("🎯 VERDICT: EXCELLENT - Data is highly accurate!")
        elif accuracy_rate >= 80:
            print("✅ VERDICT: GOOD - Data is accurate with minor deviations")
        else:
            print("⚠️  VERDICT: NEEDS REVIEW - Significant deviations detected")
    else:
        print("No results collected - check API connectivity")

    print("=" * 70)

    return results


async def test_historical_data():
    """Test historical candle endpoints."""
    print()
    print("=" * 70)
    print("HISTORICAL DATA TEST")
    print("=" * 70)

    async with httpx.AsyncClient() as client:
        for timeframe in ["1m", "5m", "1h", "1d"]:
            data = await get_historical_candles(client, timeframe, limit=3)
            if "error" in data:
                print(f"  {timeframe}: ❌ {data['error']}")
            else:
                count = data.get("count", 0)
                candles = data.get("candles", [])
                if candles:
                    latest = candles[-1] if candles else {}
                    print(f"  {timeframe}: ✅ {count} candles | Latest close: ${latest.get('c', 0):,.2f}")
                else:
                    print(f"  {timeframe}: ⚠️  No data yet")

    print("=" * 70)


async def main():
    """Main entry point."""
    # Run monitor
    results = await run_monitor()

    # Test historical endpoints
    await test_historical_data()

    return results


if __name__ == "__main__":
    asyncio.run(main())
