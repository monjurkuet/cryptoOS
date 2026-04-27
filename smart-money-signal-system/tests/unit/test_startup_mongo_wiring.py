"""Unit tests for startup Mongo wiring behavior."""

from unittest.mock import MagicMock

import pytest

from signal_system.__main__ import SignalSystem
import signal_system.api.main as api_main


class _FakeMongoClient:
    def __init__(self, *_args, **_kwargs):
        self.admin = MagicMock()
        self.admin.command = MagicMock(return_value={"ok": 1})
        self._db = MagicMock()

    def __getitem__(self, _name):
        return self._db

    def close(self):
        return None


def test_signal_system_startup_wires_mongo_outcome_store(monkeypatch):
    monkeypatch.setattr("signal_system.__main__.MongoClient", _FakeMongoClient)

    system = SignalSystem()
    stats = system.outcome_store.get_stats()

    assert stats["mongo_enabled"] is True


class _FakeSubscriber:
    def __init__(self, *_args, **_kwargs):
        self._handlers = {}

    def subscribe(self, event_type, handler):
        self._handlers[event_type] = handler

    async def connect(self):
        return None

    async def start(self):
        return None

    async def disconnect(self):
        return None

    def get_stats(self):
        return {"running": False}


@pytest.mark.asyncio
async def test_api_lifespan_wires_mongo_outcome_store(monkeypatch):
    monkeypatch.setattr("signal_system.api.main.MongoClient", _FakeMongoClient)
    monkeypatch.setattr("signal_system.api.main.EventSubscriber", _FakeSubscriber)

    async with api_main.lifespan(api_main.app):
        assert api_main._outcome_store is not None
        stats = api_main._outcome_store.get_stats()
        assert stats["mongo_enabled"] is True
