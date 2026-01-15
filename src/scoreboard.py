"""Main scoreboard application."""
import asyncio
import logging
import signal
from typing import Optional
from datetime import datetime, timedelta

from .models.config import AppConfig
from .models.game import GameState
from .api.data_fetcher import DataFetcher
from .renderers import Canvas, LiveGameRenderer, StandingsRenderer, StatsRenderer
from .utils.config_loader import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Scoreboard:
    """Main scoreboard application."""

    def __init__(self, config_path: Optional[str] = None, simulate: bool = False):
        self.config = load_config(config_path)
        # Canvas will read dimensions from environment variables
        self.canvas = Canvas()
        self.data_fetcher = DataFetcher(self.config, simulate=simulate)

        # Renderers
        self.live_game_renderer = LiveGameRenderer(self.canvas, self.config)
        self.standings_renderer = StandingsRenderer(self.canvas, self.config)
        self.stats_renderer = StatsRenderer(self.canvas, self.config)

        # State
        self.current_mode = self.config.display.default_mode
        self.current_game_index = 0
        self.last_rotation = datetime.now()
        self.running = False

    async def start(self):
        """Start the scoreboard."""
        logger.info("Starting MLB LED Scoreboard")
        self.running = True

        # Start data fetcher
        await self.data_fetcher.start()

        # Main render loop
        try:
            await self._main_loop()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the scoreboard."""
        logger.info("Stopping scoreboard")
        self.running = False
        await self.data_fetcher.stop()

    async def _main_loop(self):
        """Main rendering loop."""
        frame_delay = 1.0 / 30  # 30 FPS

        while self.running:
            start_time = asyncio.get_event_loop().time()

            try:
                await self._render_frame()
            except Exception as e:
                logger.error(f"Error rendering frame: {e}", exc_info=True)

            # Handle rotation
            if self.config.display.rotation_enabled:
                elapsed = (datetime.now() - self.last_rotation).total_seconds()
                if elapsed >= self.config.display.rotation_interval:
                    self._rotate_display()
                    self.last_rotation = datetime.now()

            # Maintain frame rate
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed < frame_delay:
                await asyncio.sleep(frame_delay - elapsed)

    async def _render_frame(self):
        """Render a single frame."""
        if self.current_mode == "live_game":
            await self._render_live_game()
        elif self.current_mode == "detailed_stats":
            await self._render_stats()
        elif self.current_mode == "standings":
            await self._render_standings()
        else:
            # Default to live game
            await self._render_live_game()

    async def _render_live_game(self):
        """Render live game mode."""
        games = self.data_fetcher.get_games()

        if not games:
            self.canvas.clear()
            self.canvas.draw_text(10, 30, "No games today", 255, 255, 255)
            self.canvas.swap()
            return

        # Prioritize live games
        live_games = self.data_fetcher.get_live_games()
        display_games = live_games if live_games else games

        # Prioritize favorite team
        fav_game = self.data_fetcher.get_favorite_game()
        if fav_game and fav_game.state == GameState.LIVE:
            display_games = [fav_game]

        if display_games:
            game_index = self.current_game_index % len(display_games)
            current_game = display_games[game_index]
            self.live_game_renderer.render(current_game)

    async def _render_stats(self):
        """Render detailed stats mode."""
        games = self.data_fetcher.get_games()

        if not games:
            self.canvas.clear()
            self.canvas.draw_text(10, 30, "No games today", 255, 255, 255)
            self.canvas.swap()
            return

        # Show stats for current game
        game_index = self.current_game_index % len(games)
        current_game = games[game_index]
        self.stats_renderer.render(current_game)

    async def _render_standings(self):
        """Render standings mode."""
        standings = self.data_fetcher.get_standings()

        if not standings:
            self.canvas.clear()
            self.canvas.draw_text(10, 30, "No standings", 255, 255, 255)
            self.canvas.swap()
            return

        self.standings_renderer.render(standings)

    def _rotate_display(self):
        """Rotate to next display."""
        games = self.data_fetcher.get_games()

        if self.current_mode == "live_game" and len(games) > 1:
            # Rotate through games
            self.current_game_index += 1
        elif self.current_mode == "standings":
            # Rotate through divisions
            self.standings_renderer.next_division()
        else:
            # Rotate through modes
            modes = [
                ("live_game", self.config.modes.live_game.enabled),
                ("detailed_stats", self.config.modes.detailed_stats.enabled),
                ("standings", self.config.modes.standings.enabled),
            ]
            enabled_modes = [mode for mode, enabled in modes if enabled]

            if enabled_modes:
                current_idx = enabled_modes.index(self.current_mode) if self.current_mode in enabled_modes else 0
                next_idx = (current_idx + 1) % len(enabled_modes)
                self.current_mode = enabled_modes[next_idx]
                logger.info(f"Switched to mode: {self.current_mode}")

    def set_mode(self, mode: str):
        """Manually set display mode."""
        self.current_mode = mode
        logger.info(f"Mode set to: {mode}")


async def main():
    """Main entry point."""
    scoreboard = Scoreboard()

    # Handle signals for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(scoreboard.stop())
        )

    await scoreboard.start()


if __name__ == "__main__":
    asyncio.run(main())
