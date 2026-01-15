#!/usr/bin/env python3
"""Main entry point for MLB LED Scoreboard."""
import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.scoreboard import Scoreboard
from src.ui.web_server import run_server, set_scoreboard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='MLB LED Scoreboard')
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file',
        default=None
    )
    parser.add_argument(
        '--web-ui',
        action='store_true',
        help='Run web UI server in addition to scoreboard'
    )
    parser.add_argument(
        '--web-ui-only',
        action='store_true',
        help='Run only the web UI server (no LED display)'
    )
    parser.add_argument(
        '--web-port',
        type=int,
        default=8080,
        help='Web UI port (default: 8080)'
    )
    parser.add_argument(
        '--web-host',
        type=str,
        default='0.0.0.0',
        help='Web UI host (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='Use simulated game data (useful for testing/off-season)'
    )

    args = parser.parse_args()

    if args.web_ui_only:
        # Run only web UI
        logger.info("Starting web UI server only")
        scoreboard = Scoreboard(config_path=args.config, simulate=args.simulate)
        run_server(scoreboard, host=args.web_host, port=args.web_port)
    else:
        # Run scoreboard
        scoreboard = Scoreboard(config_path=args.config, simulate=args.simulate)

        if args.web_ui:
            # Run web UI in background thread
            import threading
            set_scoreboard(scoreboard)
            web_thread = threading.Thread(
                target=run_server,
                args=(scoreboard, args.web_host, args.web_port),
                daemon=True
            )
            web_thread.start()
            logger.info(f"Web UI started at http://{args.web_host}:{args.web_port}")

        # Run scoreboard
        try:
            asyncio.run(scoreboard.start())
        except KeyboardInterrupt:
            logger.info("Shutting down...")


if __name__ == "__main__":
    main()
