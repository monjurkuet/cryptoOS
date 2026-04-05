# tests/unit/test_imports.py

"""Tests for lazy package imports."""

import os
import subprocess
import sys
from pathlib import Path


def _run_python(code: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run an isolated Python snippet with the project src on PYTHONPATH."""
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        f"{Path(__file__).resolve().parents[2] / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    )
    env.setdefault("MONGO__URL", "mongodb://localhost:27017")
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_importing_connector_config_does_not_build_the_fastapi_app() -> None:
    """Importing connector/config modules should not load api.main eagerly."""
    result = _run_python(
        "import sys; import market_scraper.connectors.coin_metrics.config; "
        "print('market_scraper.api.main' in sys.modules)",
        {"DEBUG": "release"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
