"""Core service layer."""

import re

from trading_watchlist.models.common import (
    EvaluateRequest,
    EvaluateResponse,
    EvaluationSummary,
    PriceResponse,
)
from trading_watchlist.models.rules import Rule
from trading_watchlist.models.state import StateBundle
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import AlertLevel, ApproachingSetup, WatchlistSummary
from trading_watchlist.parser.common import parse_float, parse_price_range
from trading_watchlist.repositories.base import TradingWatchlistRepository
from trading_watchlist.services.market_data import MarketDataService


class TradingWatchlistService:
    """Repository-backed service exposing normalized trading data."""

    def __init__(
        self,
        repository: TradingWatchlistRepository,
        market_data_service: MarketDataService,
    ) -> None:
        self._repository = repository
        self._market_data_service = market_data_service

    def get_rules(self) -> tuple[dict[str, float], list[Rule]]:
        document = self._repository.get_rules()
        return document.prices, document.rules

    def get_rule(self, rule_id: str) -> Rule | None:
        _, rules = self.get_rules()
        return next((rule for rule in rules if rule.rule_id == rule_id), None)

    def get_positions(self) -> tuple[dict[str, float], list[Position]]:
        document = self._repository.get_positions()
        return document.prices, document.positions

    def get_watchlist(self) -> tuple[dict[str, float], WatchlistSummary]:
        document = self._repository.get_watchlist()
        return document.prices, document.watchlist

    def get_approaching(self) -> list[ApproachingSetup]:
        _, watchlist = self.get_watchlist()
        return watchlist.approaching

    def get_alerts(self) -> list[AlertLevel]:
        _, watchlist = self.get_watchlist()
        return watchlist.alerts

    async def get_prices(self) -> PriceResponse:
        repository_prices = self._repository.get_prices()
        prices = dict(repository_prices.prices)
        sources = dict(repository_prices.sources)
        try:
            prices["BTC"] = await self._market_data_service.fetch_btc_price()
            sources["BTC"] = "market_api"
        except Exception:
            pass

        return PriceResponse(prices=prices, sources=sources)

    def get_state(self) -> StateBundle:
        return self._repository.get_state()

    def filter_rules(
        self, asset: str | None = None, status: str | None = None, direction: str | None = None
    ) -> list[Rule]:
        _, rules = self.get_rules()
        return [
            rule
            for rule in rules
            if self._matches_text(rule.asset, asset)
            and self._matches_text(rule.status, status, prefix=True)
            and self._matches_text(rule.direction, direction, prefix=True)
        ]

    def filter_positions(
        self, asset: str | None = None, section: str | None = None, direction: str | None = None
    ) -> list[Position]:
        _, positions = self.get_positions()
        return [
            position
            for position in positions
            if self._matches_text(position.asset, asset)
            and self._matches_text(
                position.section,
                section,
                aliases=(self._position_section_label(position.section),),
            )
            and self._matches_text(position.direction, direction, prefix=True)
        ]

    def filter_approaching(
        self, asset: str | None = None, rule_id: str | None = None
    ) -> list[ApproachingSetup]:
        return [
            setup
            for setup in self.get_approaching()
            if self._matches_asset(
                asset,
                setup.fields.get("Asset"),
                self._extract_asset_from_rule_id(setup.rule_id),
                setup.title,
                setup.summary,
            )
            and self._matches_text(setup.rule_id, rule_id)
        ]

    def filter_alerts(
        self, asset: str | None = None, priority: str | None = None
    ) -> list[AlertLevel]:
        return [
            alert
            for alert in self.get_alerts()
            if self._matches_text(alert.asset, asset)
            and self._matches_text(alert.priority, priority, prefix=True)
        ]

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        normalized_prices = await self.get_prices()
        _, rules = self.get_rules()
        prices = dict(normalized_prices.prices)
        prices.update({asset.upper(): value for asset, value in request.prices.items()})

        evaluations = [self._evaluate_rule(rule, prices.get(rule.asset.upper())) for rule in rules]
        return EvaluateResponse(prices=prices, evaluations=evaluations)

    def _matches_text(
        self,
        value: str | None,
        expected: str | None,
        *,
        prefix: bool = False,
        aliases: tuple[str | None, ...] = (),
    ) -> bool:
        if expected is None:
            return True

        normalized_expected = self._normalize_text(expected)
        for candidate in (value, *aliases):
            normalized_candidate = self._normalize_text(candidate)
            if not normalized_candidate:
                continue
            if normalized_candidate == normalized_expected:
                return True
            if prefix and normalized_candidate.startswith(normalized_expected):
                return True
        return False

    def _matches_asset(self, asset: str | None, *candidates: str | None) -> bool:
        if asset is None:
            return True

        normalized_asset = self._normalize_text(asset)
        for candidate in candidates:
            normalized_candidate = self._normalize_text(candidate)
            if not normalized_candidate:
                continue
            if normalized_candidate == normalized_asset:
                return True
            if re.search(rf"(^| ){re.escape(normalized_asset)}( |$)", normalized_candidate):
                return True
        return False

    def _position_section_label(self, section: str | None) -> str | None:
        if section == "open":
            return "Open Positions"
        if section == "pending":
            return "Pending / IN PLAY"
        return section

    def _extract_asset_from_rule_id(self, rule_id: str | None) -> str | None:
        if not rule_id:
            return None
        match = re.match(r"^[A-Z]+-\d{8}-(?P<asset>[A-Z]+)-\d+", rule_id.upper())
        return match.group("asset") if match else None

    def _normalize_text(self, value: str | None) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _evaluate_rule(self, rule: Rule, current_price: float | None) -> EvaluationSummary:
        entry_low, entry_high = parse_price_range(rule.entry or "")
        invalidation = parse_float(rule.invalidation or "")
        nearest_target = self._pick_target(rule, current_price)
        notes: list[str] = []
        state = "no-price"
        distance_to_entry_pct = None
        distance_to_invalidation_pct = None
        distance_to_target_pct = None
        target_progress_pct = None

        if current_price is not None:
            if entry_low is not None and entry_high is not None:
                if current_price < entry_low:
                    state = "below-entry-zone"
                elif current_price > entry_high:
                    state = "above-entry-zone"
                else:
                    state = "at-entry-zone"
                reference = (
                    entry_low
                    if current_price < entry_low
                    else entry_high
                    if current_price > entry_high
                    else current_price
                )
                distance_to_entry_pct = (
                    ((current_price - reference) / reference) * 100 if reference else None
                )
            else:
                state = "tracking"

            if invalidation is not None and invalidation != 0:
                distance_to_invalidation_pct = (
                    (invalidation - current_price) / current_price
                ) * 100
                if abs(distance_to_invalidation_pct) <= 3:
                    notes.append("near invalidation")

            if nearest_target is not None and current_price != 0:
                distance_to_target_pct = ((nearest_target - current_price) / current_price) * 100

            entry_reference = entry_low
            if (
                entry_reference is not None
                and nearest_target is not None
                and nearest_target != entry_reference
            ):
                progress_denominator = nearest_target - entry_reference
                if progress_denominator != 0:
                    target_progress_pct = (
                        (current_price - entry_reference) / progress_denominator
                    ) * 100
                    if rule.direction.upper().startswith("SHORT"):
                        target_progress_pct *= -1
        else:
            entry_reference = entry_low

        if nearest_target is not None:
            notes.append(f"nearest target {nearest_target:,.2f}")

        return EvaluationSummary(
            rule_id=rule.rule_id,
            asset=rule.asset,
            direction=rule.direction,
            status=rule.status,
            current_price=current_price,
            entry_reference=entry_low,
            invalidation_reference=invalidation,
            nearest_target=nearest_target,
            state=state,
            distance_to_entry_pct=distance_to_entry_pct,
            distance_to_invalidation_pct=distance_to_invalidation_pct,
            distance_to_target_pct=distance_to_target_pct,
            target_progress_pct=target_progress_pct,
            notes=notes,
        )

    def _pick_target(self, rule: Rule, current_price: float | None) -> float | None:
        candidates = [
            target.min_price
            for target in rule.targets
            if target.min_price is not None and target.status != "HIT"
        ]
        if not candidates:
            candidates = [
                target.min_price for target in rule.targets if target.min_price is not None
            ]
        if not candidates:
            return None
        if current_price is None:
            return candidates[0]
        return min(candidates, key=lambda price: abs(price - current_price))
