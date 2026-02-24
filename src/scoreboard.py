"""Main scoreboard application."""
import asyncio
import logging
import signal
from typing import Optional
from datetime import datetime, timedelta

from .models.config import AppConfig
from .models.game import GameState

_LIVE_STATES = {GameState.LIVE, GameState.IN_PROGRESS, GameState.WARMUP}
from .api.data_fetcher import DataFetcher
from .api.news_fetcher import NewsFetcher
from .renderers import Canvas, LiveGameRenderer, StandingsRenderer, StatsRenderer, NewsRenderer
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
        self.news_fetcher = NewsFetcher()

        # Renderers
        self.live_game_renderer = LiveGameRenderer(self.canvas, self.config)
        self.standings_renderer = StandingsRenderer(self.canvas, self.config)
        self.stats_renderer = StatsRenderer(self.canvas, self.config)
        self.news_renderer = NewsRenderer(self.canvas, self.config)

        # State
        self.current_mode = self.config.display.default_mode
        self.season_mode = "on"  # "on" = on-season, "off" = off-season
        self.current_game_index = 0
        self.last_rotation = datetime.now()
        self.last_news_fetch = None
        self.running = False
        self.matrix_enabled = True  # Control LED matrix on/off

    async def start(self):
        """Start the scoreboard."""
        logger.info("Starting MLB LED Scoreboard")
        self.running = True

        # Start data fetcher
        await self.data_fetcher.start()

        # Start news fetcher
        await self.news_fetcher.__aenter__()

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
        await self.news_fetcher.__aexit__(None, None, None)

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
        # Keep display cleared while matrix is disabled
        if not self.matrix_enabled:
            self.canvas.clear()
            self.canvas.swap()
            return

        if self.current_mode == "news":
            await self._render_news()
        elif self.current_mode == "live_game":
            await self._render_live_game()
        elif self.current_mode == "detailed_stats":
            await self._render_stats()
        elif self.current_mode == "standings":
            await self._render_standings()
        else:
            # Default to live game
            await self._render_live_game()

    def _get_sorted_games(self):
        """Return today's games with the favorite team's game first."""
        games = self.data_fetcher.get_games()
        fav = self.config.teams.favorite
        return sorted(
            games,
            key=lambda g: 0 if (
                g.home_team.abbreviation == fav or g.away_team.abbreviation == fav
            ) else 1
        )

    async def _render_live_game(self):
        """Render schedule cycling before games start; lock onto fav team when live."""
        games = self._get_sorted_games()  # Favorite team always at index 0

        if not games:
            self.canvas.clear()
            self.canvas.draw_text(10, 30, "No games today", 255, 255, 255)
            self.canvas.swap()
            return

        # Pinned game (user-selected from UI) takes top priority
        pinned = self.data_fetcher.get_pinned_game()
        if pinned:
            self.live_game_renderer.render(pinned)
            return

        # If the favorite team's game is live, lock onto it immediately
        fav_game = self.data_fetcher.get_favorite_game()
        if fav_game and fav_game.state in _LIVE_STATES:
            self.current_game_index = 0  # Reset so it doesn't drift
            self.live_game_renderer.render(fav_game)
            return

        # If the current slot is a finished game but live games exist,
        # jump immediately to the first live game instead of waiting for rotation.
        current = games[self.current_game_index % len(games)]
        _finished = {GameState.FINAL, GameState.GAME_OVER}
        if current.state in _finished:
            for i, g in enumerate(games):
                if g.state in _LIVE_STATES:
                    self.current_game_index = i
                    break

        game_index = self.current_game_index % len(games)
        self.live_game_renderer.render(games[game_index])

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

    async def _render_news(self):
        """Render news mode (off-season)."""
        # Fetch news every 5 minutes
        now = datetime.now()
        if self.last_news_fetch is None or (now - self.last_news_fetch).total_seconds() > 300:
            logger.info("Fetching MLB news...")
            stories = await self.news_fetcher.fetch_all_news()
            self.news_renderer.set_stories(stories)
            self.last_news_fetch = now

        self.news_renderer.render()

    def _rotate_display(self):
        """Rotate to next display."""
        # Don't rotate in off-season mode - just show news
        if self.season_mode == "off" or self.current_mode == "news":
            # In off-season mode, news renderer handles its own story rotation
            return

        games = self._get_sorted_games()

        if self.current_mode == "live_game":
            # Don't rotate when locked onto the favorite team's live game
            fav_game = self.data_fetcher.get_favorite_game()
            if fav_game and fav_game.state in _LIVE_STATES:
                return  # Stay locked on fav game
            if len(games) > 1:
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
