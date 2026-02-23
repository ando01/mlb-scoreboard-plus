"""Game data fetcher service.

Runs all HTTP fetching in a dedicated background thread (threading.Thread)
so it is completely isolated from the asyncio event loop.  The LED-matrix
render loop blocks the event loop with canvas.swap() / SwapOnVSync() calls;
any asyncio-based fetch (Task, run_in_executor) would be starved and never
complete.  A plain OS thread has no such dependency.
"""
import threading
from typing import List, Optional
from datetime import datetime
import logging
import os
from .mlb_client import MLBAPIClient
from .simulator import GameSimulator
from ..models.game import LiveGameData, GameState, StandingsEntry
from ..models.config import AppConfig

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches and caches game data in a background thread."""

    def __init__(self, config: AppConfig, simulate: bool = False):
        self.config = config
        self.simulate = simulate or os.getenv('SIMULATE_GAMES', 'false').lower() == 'true'
        self.client = MLBAPIClient()
        self.simulator = GameSimulator() if self.simulate else None

        self._lock = threading.Lock()
        self._current_games: List[LiveGameData] = []
        self._standings: List[StandingsEntry] = []

        self.refresh_interval: int = 5  # seconds between data fetches

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if self.simulate:
            logger.info("Running in SIMULATION mode - using fake game data")

    # ------------------------------------------------------------------
    # Lifecycle (async shell kept so scoreboard.py needn't change)
    # ------------------------------------------------------------------

    async def start(self):
        """Start the background data-fetch thread."""
        logger.info("Starting data fetcher thread")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._update_thread,
            name="DataFetcher",
            daemon=True,
        )
        self._thread.start()
        logger.info("Data fetcher thread started")

    async def stop(self):
        """Stop the background thread and wait for it to finish."""
        logger.info("Stopping data fetcher thread")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("Data fetcher thread stopped")

    # kept for call-site compatibility in scoreboard.py
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _update_thread(self):
        """Main loop running in the background thread."""
        logger.info("Data fetcher thread running")
        while not self._stop_event.is_set():
            try:
                self._fetch_games()
                if self.config.modes.standings.enabled:
                    self._fetch_standings()
            except Exception as e:
                logger.error(f"Error in data fetcher thread: {e}", exc_info=True)
            # Wait before next fetch, but wake immediately on stop.
            self._stop_event.wait(self.refresh_interval)
        logger.info("Data fetcher thread exiting")

    # ------------------------------------------------------------------
    # Fetch helpers (run in the background thread)
    # ------------------------------------------------------------------

    def _fetch_games(self):
        """Fetch today's games and update self._current_games."""
        logger.info(f"_fetch_games called, simulate={self.simulate}")
        try:
            if self.simulate:
                games = self.simulator.get_games()
                with self._lock:
                    self._current_games = games
                logger.info(f"Simulated {len(games)} games")
                return

            if self.config.teams.display_all:
                game_ids = self.client.get_todays_games()
            else:
                game_ids = []
                for _team in self.config.teams.preferred_teams:
                    game_ids.extend(self.client.get_todays_games())
                game_ids = list(set(game_ids))

            games = []
            for gid in game_ids:
                try:
                    game = self.client.get_game_data(gid)
                    games.append(game)
                except Exception as e:
                    logger.error(f"Failed to fetch game {gid}: {e}", exc_info=True)

            with self._lock:
                self._current_games = games
            logger.info(f"Fetched {len(games)}/{len(game_ids)} games successfully")

        except Exception as e:
            logger.error(f"Error fetching games: {e}", exc_info=True)

    def _fetch_standings(self):
        """Fetch standings and update self._standings."""
        try:
            if self.simulate:
                standings = self.simulator.get_standings()
                with self._lock:
                    self._standings = standings
                return

            all_standings = []
            for division in self.config.modes.standings.divisions:
                all_standings.extend(self.client.get_standings(division))
            with self._lock:
                self._standings = all_standings
            logger.debug(f"Fetched standings for {len(all_standings)} teams")

        except Exception as e:
            logger.error(f"Error fetching standings: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Read-only accessors (called from the asyncio render loop)
    # ------------------------------------------------------------------

    def get_games(self) -> List[LiveGameData]:
        with self._lock:
            return list(self._current_games)

    def get_standings(self) -> List[StandingsEntry]:
        with self._lock:
            return list(self._standings)

    def get_live_games(self) -> List[LiveGameData]:
        live_states = {GameState.LIVE, GameState.IN_PROGRESS, GameState.WARMUP, GameState.PREGAME}
        with self._lock:
            return [g for g in self._current_games if g.state in live_states]

    def get_favorite_game(self) -> Optional[LiveGameData]:
        fav = self.config.teams.favorite
        with self._lock:
            for game in self._current_games:
                if game.home_team.abbreviation == fav or game.away_team.abbreviation == fav:
                    return game
        return None

    # ------------------------------------------------------------------
    # Runtime simulation toggle
    # ------------------------------------------------------------------

    def set_simulation_mode(self, enabled: bool):
        """Enable or disable simulation mode at runtime."""
        if enabled == self.simulate:
            return
        self.simulate = enabled
        if enabled:
            if not self.simulator:
                self.simulator = GameSimulator()
            logger.info("Switched to SIMULATION mode")
        else:
            logger.info("Switched to LIVE mode")
        with self._lock:
            self._current_games = []
            self._standings = []

    # ------------------------------------------------------------------
    # Legacy property aliases (scoreboard.py accesses .current_games
    # and .standings directly in a few places)
    # ------------------------------------------------------------------

    @property
    def current_games(self) -> List[LiveGameData]:
        with self._lock:
            return list(self._current_games)

    @property
    def standings(self) -> List[StandingsEntry]:
        with self._lock:
            return list(self._standings)
