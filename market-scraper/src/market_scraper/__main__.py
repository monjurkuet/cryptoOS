# src/market_scraper/__main__.py

"""Market Scraper - Main entry point with CLI commands."""

import argparse
import asyncio
import sys
from typing import Any

import structlog

from market_scraper import __version__
from market_scraper.core.config import get_settings, Settings
from market_scraper.orchestration.lifecycle import LifecycleManager

logger = structlog.get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="market-scraper",
        description="Market Scraper - Real-time market data aggregation system",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start the API server")
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    server_parser.add_argument(
        "--symbol",
        default=None,
        help="Symbol to track (default: from config)",
    )
    server_parser.add_argument(
        "--no-collectors",
        action="store_true",
        help="Disable collectors (start API only)",
    )

    # Collectors command
    collectors_parser = subparsers.add_parser("collectors", help="Manage collectors")
    collectors_subparsers = collectors_parser.add_subparsers(
        dest="collectors_command",
        help="Collector actions",
    )

    # Collectors start
    start_parser = collectors_subparsers.add_parser("start", help="Start collectors")
    start_parser.add_argument(
        "--all",
        action="store_true",
        help="Start all collectors",
    )
    start_parser.add_argument(
        "names",
        nargs="*",
        help="Collector names to start",
    )

    # Collectors stop
    stop_parser = collectors_subparsers.add_parser("stop", help="Stop collectors")
    stop_parser.add_argument(
        "--all",
        action="store_true",
        help="Stop all collectors",
    )
    stop_parser.add_argument(
        "names",
        nargs="*",
        help="Collector names to stop",
    )

    # Collectors status
    collectors_subparsers.add_parser("status", help="Show collector status")

    # Traders command
    traders_parser = subparsers.add_parser("traders", help="Manage traders")
    traders_subparsers = traders_parser.add_subparsers(
        dest="traders_command",
        help="Trader actions",
    )

    # Traders track
    track_parser = traders_subparsers.add_parser("track", help="Track a trader")
    track_parser.add_argument(
        "address",
        help="Trader Ethereum address to track",
    )

    # Traders untrack
    untrack_parser = traders_subparsers.add_parser("untrack", help="Untrack a trader")
    untrack_parser.add_argument(
        "address",
        help="Trader Ethereum address to untrack",
    )

    # Traders list
    traders_subparsers.add_parser("list", help="List tracked traders")

    # Health command
    subparsers.add_parser("health", help="Check system health")

    # Config command
    subparsers.add_parser("config", help="Show current configuration")

    return parser


async def run_server(args: argparse.Namespace) -> int:
    """Run the API server.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    import uvicorn

    # Override symbol if provided
    if args.symbol:
        import os
        os.environ["HYPERLIQUID__SYMBOL"] = args.symbol

    # Set environment variable to disable collectors if requested
    if args.no_collectors:
        import os
        os.environ["HYPERLIQUID__ENABLED"] = "false"

    settings = get_settings()

    logger.info(
        "starting_server",
        host=args.host,
        port=args.port,
        symbol=settings.hyperliquid.symbol,
        workers=settings.api_workers,
    )

    config = uvicorn.Config(
        "market_scraper.api.main:app",
        host=args.host,
        port=args.port,
        workers=settings.api_workers,
        log_level="info",
    )
    server = uvicorn.Server(config)

    await server.serve()
    return 0


async def run_collectors_start(args: argparse.Namespace) -> int:
    """Start collectors.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    lifecycle = LifecycleManager()
    await lifecycle.startup()

    names = args.names if args.names else []
    if args.all:
        names = ["hyperliquid", "leaderboard"]

    for name in names:
        try:
            await lifecycle.start_connector(name)
            print(f"✓ Started collector: {name}")
        except ValueError as e:
            print(f"✗ Failed to start {name}: {e}")

    await lifecycle.shutdown()
    return 0


async def run_collectors_stop(args: argparse.Namespace) -> int:
    """Stop collectors.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    lifecycle = LifecycleManager()
    await lifecycle.startup()

    names = args.names if args.names else []
    if args.all:
        names = ["hyperliquid", "leaderboard"]

    for name in names:
        try:
            await lifecycle.stop_connector(name)
            print(f"✓ Stopped collector: {name}")
        except ValueError as e:
            print(f"✗ Failed to stop {name}: {e}")

    await lifecycle.shutdown()
    return 0


async def run_collectors_status(args: argparse.Namespace) -> int:
    """Show collector status.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    lifecycle = LifecycleManager()
    await lifecycle.startup()

    connectors = await lifecycle.list_connectors()

    print("\nCollector Status:")
    print("-" * 50)

    if not connectors:
        print("No collectors registered")
    else:
        for c in connectors:
            status_emoji = "✓" if c["status"] == "running" else "✗"
            print(f"{status_emoji} {c['name']}: {c['status']}")
            if c.get("symbol"):
                print(f"   Symbol: {c['symbol']}")

    await lifecycle.shutdown()
    return 0


async def run_traders_track(args: argparse.Namespace) -> int:
    """Track a trader.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    lifecycle = LifecycleManager()
    await lifecycle.startup()

    repository = lifecycle.repository
    if not repository:
        print("Error: Repository not available")
        await lifecycle.shutdown()
        return 1

    try:
        success = await repository.track_trader(args.address)
        if success:
            print(f"Now tracking: {args.address}")
            print("Note: Trader tracking requires trader_ws collector to be running")
        else:
            print(f"Failed to track: {args.address}")
            await lifecycle.shutdown()
            return 1
    except Exception as e:
        print(f"Error tracking trader: {e}")
        await lifecycle.shutdown()
        return 1

    await lifecycle.shutdown()
    return 0


async def run_traders_untrack(args: argparse.Namespace) -> int:
    """Untrack a trader.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    lifecycle = LifecycleManager()
    await lifecycle.startup()

    repository = lifecycle.repository
    if not repository:
        print("Error: Repository not available")
        await lifecycle.shutdown()
        return 1

    try:
        success = await repository.untrack_trader(args.address)
        if success:
            print(f"No longer tracking: {args.address}")
        else:
            print(f"Trader not found or already inactive: {args.address}")
    except Exception as e:
        print(f"Error untracking trader: {e}")
        await lifecycle.shutdown()
        return 1

    await lifecycle.shutdown()
    return 0


async def run_traders_list(args: argparse.Namespace) -> int:
    """List tracked traders.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    lifecycle = LifecycleManager()
    await lifecycle.startup()

    repository = lifecycle.repository
    if not repository:
        print("Error: Repository not available")
        await lifecycle.shutdown()
        return 1

    try:
        # Use repository method instead of direct DB access
        traders = await repository.get_tracked_traders(
            min_score=0,
            active_only=True,
            limit=20,
        )

        print("\nTracked Traders (top 20):")
        print("-" * 70)

        for t in traders:
            address = t.get("eth", t.get("address", ""))
            score = t.get("score", 0)
            name = t.get("name", t.get("displayName", ""))
            tags = t.get("tags", [])

            print(f"Score: {score:>6.1f} | {address[:20]}...")
            if name:
                print(f"           Name: {name}")
            if tags:
                print(f"           Tags: {', '.join(tags)}")
            print()

    except Exception as e:
        print(f"Error listing traders: {e}")
        await lifecycle.shutdown()
        return 1

    await lifecycle.shutdown()
    return 0


async def run_health(args: argparse.Namespace) -> int:
    """Check system health.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    lifecycle = LifecycleManager()
    await lifecycle.startup()

    health = await lifecycle.health_check()
    detailed = await lifecycle.get_detailed_health()

    print("\nSystem Health:")
    print("-" * 50)

    all_healthy = True
    for component, status in health.items():
        status_emoji = "✓" if status else "✗"
        print(f"{status_emoji} {component}: {'healthy' if status else 'unhealthy'}")
        if not status:
            all_healthy = False

    print()
    if all_healthy:
        print("All systems healthy")
    else:
        print("Some systems are unhealthy")

    await lifecycle.shutdown()
    return 0 if all_healthy else 1


async def run_config(args: argparse.Namespace) -> int:
    """Show current configuration.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    settings = get_settings()

    print("\nConfiguration:")
    print("-" * 50)
    print(f"App Version: {settings.app_version}")
    print(f"Log Level: {settings.logging.level}")
    print()
    print("Redis:")
    print(f"  URL: {settings.redis.url}")
    print()
    print("MongoDB:")
    print(f"  URL: {settings.mongo.url}")
    print(f"  Database: {settings.mongo.database}")
    print()
    print("Hyperliquid:")
    print(f"  Enabled: {settings.hyperliquid.enabled}")
    print(f"  Symbol: {settings.hyperliquid.symbol}")
    print(f"  API URL: {settings.hyperliquid.api_url}")
    print(f"  WS URL: {settings.hyperliquid.ws_url}")
    print(f"  Min Trade USD: ${settings.hyperliquid.trade_min_usd}")
    print(f"  Orderbook Threshold: {settings.hyperliquid.orderbook_price_threshold * 100}%")

    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Map commands to async functions
    command_handlers: dict[str, Any] = {
        "server": run_server,
        "collectors": {
            "start": run_collectors_start,
            "stop": run_collectors_stop,
            "status": run_collectors_status,
        },
        "traders": {
            "track": run_traders_track,
            "untrack": run_traders_untrack,
            "list": run_traders_list,
        },
        "health": run_health,
        "config": run_config,
    }

    # Get the handler
    handler = command_handlers.get(args.command)

    if isinstance(handler, dict):
        # Subcommand
        subcommand = getattr(args, f"{args.command}_command", None)
        if subcommand is None:
            parser.print_help()
            return 1
        handler = handler.get(subcommand)

    if handler is None:
        parser.print_help()
        return 1

    # Run the handler
    try:
        return asyncio.run(handler(args))
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
