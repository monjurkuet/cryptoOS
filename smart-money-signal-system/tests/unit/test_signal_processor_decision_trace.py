"""Unit tests for signal decision trace reason codes."""

import pytest

from signal_system.signal_generation.processor import SignalGenerationProcessor


def _event(address: str, szi: float) -> dict:
    return {
        "payload": {
            "address": address,
            "positions": [{"position": {"coin": "BTC", "szi": str(szi)}}],
        }
    }


@pytest.mark.asyncio
async def test_reason_emit_for_directional_signal():
    processor = SignalGenerationProcessor(symbol="BTC")
    await processor.process_position(_event("0x1", 10.0))

    trace = processor.get_latest_decision_trace()
    assert trace is not None
    assert trace["result"] == "emitted"
    assert trace["reason_code"] == "emit"


@pytest.mark.asyncio
async def test_reason_duplicate_signal_for_no_change():
    processor = SignalGenerationProcessor(symbol="BTC")
    await processor.process_position(_event("0x1", 10.0))
    await processor.process_position(_event("0x1", 10.0))

    trace = processor.get_latest_decision_trace()
    assert trace is not None
    assert trace["result"] == "suppressed"
    assert trace["reason_code"] == "duplicate_signal"


@pytest.mark.asyncio
async def test_reason_threshold_not_met_for_emitted_neutral():
    processor = SignalGenerationProcessor(symbol="BTC", min_confidence=0.0)
    await processor.process_position(_event("0x1", 10.0))
    await processor.process_position(_event("0x2", -10.0))

    trace = processor.get_latest_decision_trace()
    assert trace is not None
    assert trace["action"] == "NEUTRAL"
    assert trace["result"] == "emitted"
    assert trace["reason_code"] == "threshold_not_met"


@pytest.mark.asyncio
async def test_reason_min_confidence_not_met_for_suppressed_signal():
    processor = SignalGenerationProcessor(symbol="BTC", min_confidence=0.8)
    await processor.process_position(_event("0x1", 10.0))
    await processor.process_position(_event("0x2", -10.0))

    trace = processor.get_latest_decision_trace()
    assert trace is not None
    assert trace["result"] == "suppressed"
    assert trace["reason_code"] == "min_confidence_not_met"
