"""Generated markdown scaffolds derived from canonical state."""

from collections.abc import Iterable
from pathlib import Path

from trading_watchlist.models.state import StateBundle


class GeneratedMarkdownWriter:
    """Render scaffold markdown reports from canonical state."""

    file_names = {
        "rules": "analysis-rules.generated.md",
        "trades": "analysis-trades.generated.md",
        "watchlist": "analysis-watchlist.generated.md",
        "brief": "analysis-brief.generated.md",
    }

    def write(self, state: StateBundle, output_dir: Path) -> list[Path]:
        """Write generated markdown scaffold files."""

        output_dir.mkdir(parents=True, exist_ok=True)
        documents = self.render(state)

        written_paths: list[Path] = []
        for name, content in documents.items():
            path = output_dir / self.file_names[name]
            path.write_text(content, encoding="utf-8")
            written_paths.append(path)
        return written_paths

    def render(self, state: StateBundle) -> dict[str, str]:
        """Render scaffold markdown content keyed by report type."""

        return {
            "rules": self._render_rules(state),
            "trades": self._render_trades(state),
            "watchlist": self._render_watchlist(state),
            "brief": self._render_brief(state),
        }

    def _render_rules(self, state: StateBundle) -> str:
        lines = self._header(
            title="Rules Report Scaffold",
            state=state,
            summary_lines=[
                f"- Total rules: {len(state.rules)}",
                f"- Active prices tracked: {len(state.prices)}",
            ],
        )
        lines.extend(
            [
                "## Current Prices",
                "",
                *self._bullet_lines(
                    f"`{asset}`: {value}" for asset, value in sorted(state.prices.items())
                ),
                "",
                "## Rules",
                "",
            ]
        )
        if not state.rules:
            lines.extend(["No rules available.", ""])
        else:
            for rule in state.rules:
                target_summary = ", ".join(target.value_text for target in rule.targets) or "None"
                lines.extend(
                    [
                        f"### {rule.rule_id}",
                        "",
                        f"- Asset: `{rule.asset}`",
                        f"- Direction: `{rule.direction}`",
                        f"- Status: `{rule.status}`",
                        f"- Timeframe: `{rule.timeframe or 'n/a'}`",
                        f"- Entry: {rule.entry or 'n/a'}",
                        f"- Targets: {target_summary}",
                        f"- Invalidation: {rule.invalidation or 'n/a'}",
                        f"- Notes: {rule.notes or 'Placeholder for generated rule commentary.'}",
                        "",
                    ]
                )
        return "\n".join(lines).rstrip() + "\n"

    def _render_trades(self, state: StateBundle) -> str:
        open_positions = [position for position in state.positions if position.section == "open"]
        lines = self._header(
            title="Trades Report Scaffold",
            state=state,
            summary_lines=[
                f"- Total tracked positions: {len(state.positions)}",
                f"- Open positions: {len(open_positions)}",
            ],
        )
        lines.extend(["## Positions", ""])
        if not state.positions:
            lines.extend(["No positions available.", ""])
        else:
            for position in state.positions:
                lines.extend(
                    [
                        f"### {position.title}",
                        "",
                        f"- Rule ID: `{position.rule_id}`",
                        f"- Section: `{position.section}`",
                        f"- Asset: `{position.asset or 'n/a'}`",
                        f"- Direction: `{position.direction or 'n/a'}`",
                        f"- Status: `{position.status or 'n/a'}`",
                        "- Summary: Placeholder for generated trade execution notes.",
                        "",
                    ]
                )
        return "\n".join(lines).rstrip() + "\n"

    def _render_watchlist(self, state: StateBundle) -> str:
        watchlist = state.watchlist
        lines = self._header(
            title="Watchlist Report Scaffold",
            state=state,
            summary_lines=[
                f"- Approaching setups: {len(watchlist.approaching)}",
                f"- Future setups: {len(watchlist.future_setups)}",
                f"- Alerts: {len(watchlist.alerts)}",
            ],
        )
        lines.extend(["## Approaching Setups", ""])
        lines.extend(self._render_setup_list(watchlist.approaching))
        lines.extend(["## Future Setups", ""])
        lines.extend(self._render_setup_list(watchlist.future_setups))
        lines.extend(["## Alerts", ""])
        if not watchlist.alerts:
            lines.extend(["No alert levels available.", ""])
        else:
            for alert in watchlist.alerts:
                lines.extend(
                    [
                        f"- `{alert.asset}` {alert.direction} at {alert.price}: {alert.trigger} ({alert.priority})",
                    ]
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_brief(self, state: StateBundle) -> str:
        lines = self._header(
            title="Brief Report Scaffold",
            state=state,
            summary_lines=[
                f"- Rules: {len(state.rules)}",
                f"- Positions: {len(state.positions)}",
                f"- Watchlist alerts: {len(state.watchlist.alerts)}",
            ],
        )
        lines.extend(
            [
                "## Market Snapshot",
                "",
                *self._bullet_lines(
                    f"`{asset}`: {value}" for asset, value in sorted(state.prices.items())
                ),
                "",
                "## Generated Notes",
                "",
                "- This scaffold is generated from `state.json` and is safe to overwrite.",
                "- Human-authored markdown remains the source input during the fallback phase.",
                "- Replace placeholder commentary after the markdown renderer becomes authoritative.",
                "",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    def _render_setup_list(self, setups: list) -> list[str]:
        if not setups:
            return ["No setups available.", ""]

        lines: list[str] = []
        for setup in setups:
            asset = setup.fields.get("Asset", "n/a")
            lines.extend(
                [
                    f"### {setup.title}",
                    "",
                    f"- Rule ID: `{setup.rule_id or 'n/a'}`",
                    f"- Asset: `{asset}`",
                    f"- Summary: {setup.summary or 'Placeholder for generated watchlist commentary.'}",
                    "",
                ]
            )
        return lines

    def _header(self, *, title: str, state: StateBundle, summary_lines: Iterable[str]) -> list[str]:
        return [
            f"# {title}",
            "",
            "_Generated scaffold from canonical structured state. Do not hand-edit; regenerate instead._",
            "",
            f"- Generated at: `{state.generated_at.isoformat()}`",
            f"- Source mode: `{state.metadata.source_mode}`",
            f"- Schema version: `{state.schema_version}`",
            *summary_lines,
            "",
        ]

    def _bullet_lines(self, items: Iterable[str]) -> list[str]:
        lines = [f"- {item}" for item in items]
        if lines:
            return lines
        return ["- No data available."]
