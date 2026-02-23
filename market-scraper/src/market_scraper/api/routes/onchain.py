# src/market_scraper/api/routes/onchain.py

"""Unified on-chain metrics API endpoints.

This module provides a unified API for Bitcoin on-chain metrics by aggregating
data from multiple sources:
- BlockchainInfoConnector: Network stats (hash rate, difficulty, transactions)
- FearGreedConnector: Market sentiment
- CoinMetricsConnector: Price, market cap, active addresses
- CBBIConnector: Valuation metrics (MVRV, Puell, NUPL, etc.)
- ChainExposedConnector: SOPR, NUPL, MVRV, HODL Waves, Dormancy
- ExchangeFlowConnector: Exchange inflows/outflows, netflow
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from market_scraper.api.dependencies import get_all_connectors

logger = structlog.get_logger(__name__)

router = APIRouter()


# Response models
class NetworkMetrics(BaseModel):
    """Network metrics from Blockchain.info."""

    hash_rate_ghs: float | None = Field(None, description="Network hash rate in GH/s")
    difficulty: float | None = Field(None, description="Mining difficulty")
    block_height: int | None = Field(None, description="Current block height")
    total_btc: float | None = Field(None, description="Total BTC in circulation")


class FearGreedData(BaseModel):
    """Fear & Greed Index data."""

    value: int | None = Field(None, description="Index value (0-100)")
    classification: str | None = Field(None, description="Sentiment classification")


class SentimentMetrics(BaseModel):
    """Sentiment metrics from multiple sources."""

    fear_greed: FearGreedData = Field(default_factory=FearGreedData)
    cbbi_confidence: float | None = Field(None, description="CBBI confidence score (0-1)")


class SOPRMetrics(BaseModel):
    """SOPR metrics from ChainExposed."""

    sopr: float | None = Field(None, description="Spent Output Profit Ratio")
    interpretation: str | None = Field(None, description="profit_taking or loss_realization")
    sth_sopr: float | None = Field(None, description="Short-term holder SOPR")
    lth_sopr: float | None = Field(None, description="Long-term holder SOPR")


class ExchangeFlowMetrics(BaseModel):
    """Exchange flow metrics from Coin Metrics."""

    flow_in_btc: float | None = Field(None, description="BTC flowing into exchanges")
    flow_out_btc: float | None = Field(None, description="BTC flowing out of exchanges")
    netflow_btc: float | None = Field(None, description="Net flow (outflow - inflow)")
    supply_btc: float | None = Field(None, description="Total BTC on exchanges")
    interpretation: str | None = Field(None, description="bullish or bearish")


class ActivityMetrics(BaseModel):
    """Activity metrics from Coin Metrics."""

    active_addresses: float | None = Field(None, description="Daily active addresses")
    transaction_count: float | None = Field(None, description="Daily transaction count")
    supply: float | None = Field(None, description="Current BTC supply")
    market_cap: float | None = Field(None, description="Market capitalization in USD")


class OnchainSummaryResponse(BaseModel):
    """Unified on-chain metrics summary."""

    timestamp: str = Field(..., description="When data was fetched")
    price_usd: float | None = Field(None, description="Current BTC price in USD")
    network: NetworkMetrics = Field(default_factory=NetworkMetrics)
    sentiment: SentimentMetrics = Field(default_factory=SentimentMetrics)
    valuation: dict[str, float] = Field(
        default_factory=dict,
        description="CBBI valuation components (MVRV, Puell, etc.)",
    )
    activity: ActivityMetrics = Field(default_factory=ActivityMetrics)
    sopr: SOPRMetrics = Field(default_factory=SOPRMetrics)
    exchange_flows: ExchangeFlowMetrics = Field(default_factory=ExchangeFlowMetrics)


@router.get("/btc/summary", response_model=OnchainSummaryResponse)
async def get_onchain_summary() -> dict[str, Any]:
    """Get unified Bitcoin on-chain metrics summary.

    Aggregates data from multiple sources into a single comprehensive response:

    - **Network**: Hash rate, difficulty, block height (Blockchain.info)
    - **Sentiment**: Fear & Greed Index, CBBI confidence
    - **Valuation**: MVRV, Puell, NUPL, Reserve Risk, etc. (CBBI)
    - **Activity**: Active addresses, transaction count, supply (Coin Metrics)
    - **SOPR**: Spent Output Profit Ratio with LTH/STH variants (ChainExposed)
    - **Exchange Flows**: Inflow, outflow, netflow, supply (Coin Metrics CSV)

    All data is fetched in parallel for optimal performance.
    """
    try:
        # Use dependency injection
        connectors = await get_all_connectors()
        blockchain, fear_greed, coin_metrics, cbbi, chainexposed, exchange_flow = connectors

        # Fetch all data in parallel for speed
        network_task = blockchain.get_current_metrics()
        sentiment_task = fear_greed.get_current_index()
        activity_task = coin_metrics.get_latest_metrics()
        cbbi_task = cbbi.get_current_index()
        sopr_task = chainexposed.get_summary()
        flow_task = exchange_flow.get_current_flows()

        results = await asyncio.gather(
            network_task,
            sentiment_task,
            activity_task,
            cbbi_task,
            sopr_task,
            flow_task,
            return_exceptions=True,
        )

        network, sentiment, activity, cbbi_data, sopr_data, flow_data = results

        # Build response
        response = {
            "timestamp": datetime.now(UTC).isoformat(),
            "price_usd": None,
            "network": {},
            "sentiment": {"fear_greed": {}, "cbbi_confidence": None},
            "valuation": {},
            "activity": {},
            "sopr": {},
            "exchange_flows": {},
        }

        # Process network data
        if not isinstance(network, Exception):
            response["network"] = {
                "hash_rate_ghs": network.payload.get("hash_rate_ghs"),
                "difficulty": network.payload.get("difficulty"),
                "block_height": network.payload.get("block_height"),
                "total_btc": network.payload.get("total_btc"),
            }
            response["price_usd"] = network.payload.get("price_usd")
        else:
            logger.warning("onchain_network_fetch_failed", error=str(network))

        # Process sentiment data
        if not isinstance(sentiment, Exception):
            response["sentiment"]["fear_greed"] = {
                "value": sentiment.payload.get("value"),
                "classification": sentiment.payload.get("classification"),
            }
        else:
            logger.warning("onchain_sentiment_fetch_failed", error=str(sentiment))

        # Process CBBI data
        if not isinstance(cbbi_data, Exception):
            response["sentiment"]["cbbi_confidence"] = cbbi_data.payload.get("confidence")
            response["valuation"] = cbbi_data.payload.get("components", {})
            if response["price_usd"] is None:
                response["price_usd"] = cbbi_data.payload.get("price")
        else:
            logger.warning("onchain_cbbi_fetch_failed", error=str(cbbi_data))

        # Process activity data
        if not isinstance(activity, Exception):
            metrics = activity.payload.get("metrics", {})
            response["activity"] = {
                "active_addresses": metrics.get("AdrActCnt"),
                "transaction_count": metrics.get("TxCnt"),
                "supply": metrics.get("SplyCur"),
                "market_cap": metrics.get("CapMrktCurUSD"),
            }
        else:
            logger.warning("onchain_activity_fetch_failed", error=str(activity))

        # Process SOPR data
        if not isinstance(sopr_data, Exception):
            sopr = sopr_data.get("sopr", {})
            sth = sopr_data.get("sopr_sth", {})
            lth = sopr_data.get("sopr_lth", {})
            response["sopr"] = {
                "sopr": sopr.get("value"),
                "interpretation": sopr.get("interpretation"),
                "sth_sopr": sth.get("value"),
                "lth_sopr": lth.get("value"),
            }
        else:
            logger.warning("onchain_sopr_fetch_failed", error=str(sopr_data))

        # Process exchange flow data
        if not isinstance(flow_data, Exception):
            response["exchange_flows"] = {
                "flow_in_btc": flow_data.payload.get("flow_in_btc"),
                "flow_out_btc": flow_data.payload.get("flow_out_btc"),
                "netflow_btc": flow_data.payload.get("netflow_btc"),
                "supply_btc": flow_data.payload.get("supply_btc"),
                "interpretation": flow_data.payload.get("netflow_interpretation"),
            }
        else:
            logger.warning("onchain_flow_fetch_failed", error=str(flow_data))

        logger.info("onchain_summary_fetched", price=response.get("price_usd"))

        return response

    except Exception as e:
        logger.error("onchain_summary_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch on-chain data: {str(e)}",
        ) from e


@router.get("/btc/network")
async def get_network_metrics() -> dict[str, Any]:
    """Get Bitcoin network metrics from Blockchain.info.

    Returns:
    - **hash_rate_ghs**: Network hash rate in GH/s (divide by 1e9 for TH/s)
    - **difficulty**: Current mining difficulty
    - **block_height**: Current block height
    - **total_btc**: Total BTC in circulation
    - **price_usd**: 24-hour average price
    - **market_cap_usd**: Market capitalization
    """
    try:
        connectors = await get_all_connectors()
        blockchain = connectors[0]
        event = await blockchain.get_current_metrics()
        logger.info("onchain_network_fetched", block_height=event.payload.get("block_height"))
        return event.payload
    except Exception as e:
        logger.error("onchain_network_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch network metrics: {str(e)}",
        ) from e


@router.get("/btc/sentiment")
async def get_sentiment_metrics() -> dict[str, Any]:
    """Get sentiment metrics from Fear & Greed and CBBI.

    Returns:
    - **fear_greed**: Fear & Greed Index (0-100)
      - 0-20: Extreme Fear (potential buying opportunity)
      - 20-40: Fear
      - 40-60: Neutral
      - 60-80: Greed
      - 80-100: Extreme Greed (potential selling opportunity)
    - **cbbi**: CBBI confidence score and components
    """
    try:
        connectors = await get_all_connectors()
        _, fear_greed, _, cbbi, _, _ = connectors

        fg_task = fear_greed.get_current_index()
        cbbi_task = cbbi.get_current_index()

        fg, cbbi_data = await asyncio.gather(fg_task, cbbi_task, return_exceptions=True)

        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "fear_greed": None,
            "cbbi": None,
        }

        if not isinstance(fg, Exception):
            result["fear_greed"] = fg.payload

        if not isinstance(cbbi_data, Exception):
            result["cbbi"] = cbbi_data.payload

        logger.info("onchain_sentiment_fetched")
        return result

    except Exception as e:
        logger.error("sentiment_metrics_fetch_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch sentiment metrics: {str(e)}",
        ) from e


@router.get("/btc/valuation")
async def get_valuation_metrics() -> dict[str, Any]:
    """Get Bitcoin valuation metrics from CBBI.

    CBBI aggregates multiple on-chain metrics into a confidence score.

    Returns all component metrics:
    - **PiCycle**: Pi Cycle Top Indicator
    - **RUPL**: Relative Unrealized Profit/Loss
    - **RHODL**: Realized HODL Ratio
    - **Puell**: Puell Multiple
    - **2YMA**: 2-Year Moving Average
    - **MVRV**: MVRV Z-Score
    - **ReserveRisk**: Reserve Risk
    - **Woobull**: Top Cap vs CVDD
    - **Trolololo**: Bitcoin Trolololo
    """
    try:
        connectors = await get_all_connectors()
        cbbi = connectors[3]
        event = await cbbi.get_current_index()

        result = {
            "timestamp": event.payload.get("timestamp"),
            "confidence": event.payload.get("confidence"),
            "price": event.payload.get("price"),
            "components": event.payload.get("components", {}),
        }

        logger.info("onchain_valuation_fetched", confidence=result.get("confidence"))
        return result

    except Exception as e:
        logger.error("valuation_metrics_fetch_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch valuation metrics: {str(e)}",
        ) from e


@router.get("/btc/activity")
async def get_activity_metrics() -> dict[str, Any]:
    """Get Bitcoin activity metrics from Coin Metrics.

    Returns:
    - **PriceUSD**: Current price in USD
    - **CapMrktCurUSD**: Market capitalization
    - **AdrActCnt**: Daily active addresses
    - **TxCnt**: Daily transaction count
    - **BlkCnt**: Daily block count
    - **SplyCur**: Current circulating supply
    """
    try:
        connectors = await get_all_connectors()
        coin_metrics = connectors[2]
        event = await coin_metrics.get_latest_metrics()

        result = {
            "timestamp": event.payload.get("timestamp"),
            "metrics": event.payload.get("metrics", {}),
        }

        logger.info("onchain_activity_fetched")
        return result

    except Exception as e:
        logger.error("activity_metrics_fetch_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch activity metrics: {str(e)}",
        ) from e


@router.get("/btc/sopr")
async def get_sopr_metrics() -> dict[str, Any]:
    """Get SOPR (Spent Output Profit Ratio) metrics from ChainExposed.

    SOPR measures whether coins are being sold at profit or loss:
    - **SOPR > 1**: Coins being sold at profit
    - **SOPR < 1**: Coins being sold at loss

    Returns:
    - **sopr**: Overall SOPR
    - **sth_sopr**: Short-term holder SOPR (coins < 155 days)
    - **lth_sopr**: Long-term holder SOPR (coins > 155 days)
    - **interpretation**: profit_taking or loss_realization
    """
    try:
        connectors = await get_all_connectors()
        chainexposed = connectors[4]

        # Fetch all SOPR variants in parallel
        sopr_task = chainexposed.get_sopr()
        sth_task = chainexposed.get_sopr_sth()
        lth_task = chainexposed.get_sopr_lth()

        sopr, sth, lth = await asyncio.gather(sopr_task, sth_task, lth_task, return_exceptions=True)

        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "sopr": None,
            "sth_sopr": None,
            "lth_sopr": None,
        }

        if not isinstance(sopr, Exception):
            result["sopr"] = {
                "value": sopr.payload.get("value"),
                "date": sopr.payload.get("date"),
                "interpretation": sopr.payload.get("interpretation"),
            }

        if not isinstance(sth, Exception):
            result["sth_sopr"] = {
                "value": sth.payload.get("value"),
                "date": sth.payload.get("date"),
            }

        if not isinstance(lth, Exception):
            result["lth_sopr"] = {
                "value": lth.payload.get("value"),
                "date": lth.payload.get("date"),
            }

        logger.info("onchain_sopr_fetched", sopr=result.get("sopr", {}).get("value"))
        return result

    except Exception as e:
        logger.error("sopr_metrics_fetch_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch SOPR metrics: {str(e)}",
        ) from e


@router.get("/btc/exchange-flows")
async def get_exchange_flows() -> dict[str, Any]:
    """Get Bitcoin exchange flow metrics from Coin Metrics.

    Exchange flows track BTC movement to/from exchanges:
    - **Positive netflow**: BTC leaving exchanges (bullish)
    - **Negative netflow**: BTC entering exchanges (bearish)

    Returns:
    - **flow_in_btc**: BTC flowing into exchanges
    - **flow_out_btc**: BTC flowing out of exchanges
    - **netflow_btc**: Net flow (outflow - inflow)
    - **supply_btc**: Total BTC on exchanges
    - **interpretation**: bullish or bearish
    """
    try:
        connectors = await get_all_connectors()
        exchange_flow = connectors[5]

        # Get current flows
        flows_task = exchange_flow.get_current_flows()
        summary_task = exchange_flow.get_netflow_summary()

        flows, summary = await asyncio.gather(flows_task, summary_task, return_exceptions=True)

        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "flow_in_btc": None,
            "flow_out_btc": None,
            "netflow_btc": None,
            "supply_btc": None,
            "interpretation": None,
            "statistics": {},
        }

        if not isinstance(flows, Exception):
            result["flow_in_btc"] = flows.payload.get("flow_in_btc")
            result["flow_out_btc"] = flows.payload.get("flow_out_btc")
            result["netflow_btc"] = flows.payload.get("netflow_btc")
            result["supply_btc"] = flows.payload.get("supply_btc")
            result["interpretation"] = flows.payload.get("netflow_interpretation")

        if not isinstance(summary, Exception):
            result["statistics"] = {
                "netflow_7d_avg": summary.get("netflow_7d_avg"),
                "netflow_30d_avg": summary.get("netflow_30d_avg"),
                "cumulative_netflow_7d": summary.get("cumulative_netflow_7d"),
            }

        logger.info("onchain_exchange_flows_fetched", netflow=result.get("netflow_btc"))
        return result

    except Exception as e:
        logger.error("exchange_flows_fetch_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch exchange flows: {str(e)}",
        ) from e


@router.get("/btc/nupl")
async def get_nupl_metrics() -> dict[str, Any]:
    """Get NUPL (Net Unrealized Profit/Loss) from ChainExposed.

    NUPL zones:
    - **< 0**: Capitulation
    - **0 - 0.25**: Hope/Fear
    - **0.25 - 0.5**: Optimism
    - **0.5 - 0.75**: Belief
    - **> 0.75**: Euphoria
    """
    try:
        connectors = await get_all_connectors()
        chainexposed = connectors[4]
        event = await chainexposed.get_nupl()

        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": event.payload.get("value"),
            "date": event.payload.get("date"),
            "zone": event.payload.get("zone"),
            "statistics": event.payload.get("statistics", {}),
        }

        logger.info("onchain_nupl_fetched", value=result.get("value"))
        return result

    except Exception as e:
        logger.error("nupl_metrics_fetch_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch NUPL metrics: {str(e)}",
        ) from e


@router.get("/btc/mvrv")
async def get_mvrv_metrics() -> dict[str, Any]:
    """Get MVRV (Market Value to Realized Value) from ChainExposed.

    MVRV signals:
    - **< 1.0**: Undervalued (historical buying opportunity)
    - **> 3.5**: Overvalued (historical selling opportunity)
    """
    try:
        connectors = await get_all_connectors()
        chainexposed = connectors[4]
        event = await chainexposed.get_mvrv()

        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "value": event.payload.get("value"),
            "date": event.payload.get("date"),
            "signal": event.payload.get("signal"),
            "statistics": event.payload.get("statistics", {}),
        }

        logger.info("onchain_mvrv_fetched", value=result.get("value"))
        return result

    except Exception as e:
        logger.error("mvrv_metrics_fetch_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch MVRV metrics: {str(e)}",
        ) from e


@router.get("/health")
async def onchain_health() -> dict[str, Any]:
    """Check health of all on-chain data connectors."""
    try:
        connectors = await get_all_connectors()
        (
            blockchain,
            fear_greed,
            coin_metrics,
            cbbi,
            chainexposed,
            exchange_flow,
        ) = connectors

        # Run all health checks in parallel
        results = await asyncio.gather(
            blockchain.health_check(),
            fear_greed.health_check(),
            coin_metrics.health_check(),
            cbbi.health_check(),
            chainexposed.health_check(),
            exchange_flow.health_check(),
            return_exceptions=True,
        )

        health_status = {
            "timestamp": datetime.now(UTC).isoformat(),
            "connectors": {
                "blockchain_info": results[0]
                if not isinstance(results[0], Exception)
                else {"status": "unhealthy", "error": str(results[0])},
                "fear_greed": results[1]
                if not isinstance(results[1], Exception)
                else {"status": "unhealthy", "error": str(results[1])},
                "coin_metrics": results[2]
                if not isinstance(results[2], Exception)
                else {"status": "unhealthy", "error": str(results[2])},
                "cbbi": results[3]
                if not isinstance(results[3], Exception)
                else {"status": "unhealthy", "error": str(results[3])},
                "chainexposed": results[4]
                if not isinstance(results[4], Exception)
                else {"status": "unhealthy", "error": str(results[4])},
                "exchange_flow": results[5]
                if not isinstance(results[5], Exception)
                else {"status": "unhealthy", "error": str(results[5])},
            },
        }

        # Overall status
        all_healthy = all(
            r.get("status") == "healthy" if isinstance(r, dict) else False
            for r in health_status["connectors"].values()
        )
        health_status["status"] = "healthy" if all_healthy else "degraded"

        return health_status

    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }
