"""
Tests for data models.
"""

import pytest
from datetime import datetime

from src.models.btc_market import BtcCandle, BtcOrderbook, BtcTrade, BtcTicker
from src.models.traders import TrackedTrader, TraderPerformances, WindowPerformance
from src.models.signals import BtcSignal, AggregatedBtcSignal


class TestBtcMarketModels:
    """Tests for BTC market models."""

    def test_btc_candle_model(self):
        """Test BtcCandle model creation."""
        candle = BtcCandle(
            t=datetime.utcnow(),
            interval="1h",
            o=75000.0,
            h=75100.0,
            l=74900.0,
            c=75050.0,
            v=150.5,
        )

        assert candle.interval == "1h"
        assert candle.o == 75000.0
        assert candle.v == 150.5

    def test_btc_orderbook_model(self):
        """Test BtcOrderbook model creation."""
        orderbook = BtcOrderbook(
            t=datetime.utcnow(),
            bids=[{"px": 75000.0, "sz": 1.5, "n": 3}],
            asks=[{"px": 75010.0, "sz": 2.0, "n": 5}],
            spread=10.0,
            midPrice=75005.0,
            bidDepth=1.5,
            askDepth=2.0,
            imbalance=-0.1428,
        )

        assert orderbook.spread == 10.0
        assert len(orderbook.bids) == 1

    def test_btc_trade_model(self):
        """Test BtcTrade model creation."""
        trade = BtcTrade(
            tid=123456789,
            t=datetime.utcnow(),
            px=75000.0,
            sz=0.5,
            side="B",
            hash="0xabc123",
            usdValue=37500.0,
        )

        assert trade.tid == 123456789
        assert trade.side == "B"

    def test_btc_ticker_model(self):
        """Test BtcTicker model creation."""
        ticker = BtcTicker(
            t=datetime.utcnow(),
            px=75000.0,
            lastSz=0.1,
            volume24h=10000000.0,
            trades24h=5000,
            high24h=76000.0,
            low24h=74000.0,
        )

        assert ticker.px == 75000.0
        assert ticker.volume24h == 10000000.0


class TestTraderModels:
    """Tests for trader models."""

    def test_window_performance_model(self):
        """Test WindowPerformance model."""
        perf = WindowPerformance(
            pnl=100000.0,
            roi=0.15,
            vlm=5000000.0,
        )

        assert perf.pnl == 100000.0
        assert perf.roi == 0.15

    def test_trader_performances_model(self):
        """Test TraderPerformances model."""
        perfs = TraderPerformances(
            day=WindowPerformance(pnl=1000, roi=0.01, vlm=100000),
            week=WindowPerformance(pnl=5000, roi=0.05, vlm=500000),
            month=WindowPerformance(pnl=20000, roi=0.20, vlm=2000000),
            allTime=WindowPerformance(pnl=100000, roi=1.0, vlm=10000000),
        )

        assert perfs.day.pnl == 1000
        assert perfs.allTime.roi == 1.0


class TestSignalModels:
    """Tests for signal models."""

    def test_btc_signal_model(self):
        """Test BtcSignal model creation."""
        signal = BtcSignal(
            t=datetime.utcnow(),
            signalType="position_change",
            ethAddress="0x123...",
            coin="BTC",
            direction="long",
            size=1.5,
            confidence=0.75,
            price=75000.0,
        )

        assert signal.signalType == "position_change"
        assert signal.direction == "long"
        assert signal.confidence == 0.75

    def test_aggregated_signal_model(self):
        """Test AggregatedBtcSignal model creation."""
        signal = AggregatedBtcSignal(
            t=datetime.utcnow(),
            longScore=25.5,
            shortScore=10.2,
            totalWeight=40.0,
            tradersLong=50,
            tradersShort=20,
            tradersFlat=30,
            netExposure=15.3,
            longBias=0.6375,
            shortBias=0.255,
            recommendation="LONG",
            confidence=0.68,
            price=75000.0,
        )

        assert signal.recommendation == "LONG"
        assert signal.tradersLong == 50
        assert signal.confidence == 0.68
