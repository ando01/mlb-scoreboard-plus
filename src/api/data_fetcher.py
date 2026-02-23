"""Game data fetcher service.

Runs all HTTP fetching in a dedicated background thread (threading.Thread)
so it is completely isolated from the asyncio event loop.  The LED-matrix
render loop blocks the event loop with canvas.swap() / SwapOnVSync() calls;
any asyncio-based fetch (Task, run_in_executor) would be starved and never
complete.  A plain OS thread has no such dependency.
"""
import threading
from typing import List, Optional, Set
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
        self.pinned_game_id: Optional[int] = None

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

    def set_pinned_game(self, game_id: Optional[int]):
        """Pin a specific game to show on the board. Pass None to auto-select."""
        self.pinned_game_id = game_id
        # Clear current games so the next fetch immediately picks up the new game
        with self._lock:
            self._current_games = []

    def get_pinned_game(self) -> Optional[LiveGameData]:
        """Return the pinned game's data, or None if no pin is set."""
        if self.pinned_game_id is None:
            return None
        with self._lock:
            for game in self._current_games:
                if game.game_id == self.pinned_game_id:
                    return game
        return None

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
        """Fetch game data with a two-tier strategy:

        Tier 1 (every ~30 s, one API call):
            Schedule endpoint with linescore+probablePitchers hydration.
            Gives us teams, state, score, and inning for ALL games cheaply.

        Tier 2 (every refresh_interval, one API call):
            Full /feed/live for only the single game currently on the board.
            This is the only data that needs to be real-time.
        """
        try:
            if self.simulate:
                games = self.simulator.get_games()
                with self._lock:
                    self._current_games = games
                logger.info(f"Simulated {len(games)} games")
                return

            today = datetime.now().strftime("%Y-%m-%d")

            # --- Tier 1: lightweight schedule fetch (all games, cached 30 s) ---
            all_games = self.client.get_schedule_with_details(today)

            if not all_games:
                with self._lock:
                    self._current_games = []
                return

            # --- Tier 2: full live feed for the active game only ---
            # Search the FULL schedule for live games — filter comes after.
            # Priority: pinned > live favorite > any live game
            _live = {GameState.LIVE, GameState.IN_PROGRESS, GameState.WARMUP}
            fav = self.config.teams.favorite

            active_id = self.pinned_game_id
            if active_id is None:
                for g in all_games:
                    if g.state in _live and (
                        g.home_team.abbreviation == fav
                        or g.away_team.abbreviation == fav
                    ):
                        active_id = g.game_id
                        break
            if active_id is None:
                for g in all_games:
                    if g.state in _live:
                        active_id = g.game_id
                        break

            if active_id is not None:
                try:
                    live = self.client.get_game_data(active_id)
                    all_games = [
                        live if g.game_id == active_id else g
                        for g in all_games
                    ]
                    logger.info(f"Live feed fetched for game {active_id}")
                except Exception as e:
                    logger.error(f"Live feed fetch failed for {active_id}: {e}", exc_info=True)
            else:
                logger.info("No live games — using schedule data only")

            # Filter to preferred teams when display_all is off — but ONLY
            # when a preferred team is actually live right now.  If no
            # preferred game is in progress, show the full schedule so the
            # board always has live content to display.
            if not self.config.teams.display_all:
                preferred: Set[str] = set(self.config.teams.preferred_teams)
                pref_games = [
                    g for g in all_games
                    if g.home_team.abbreviation in preferred
                    or g.away_team.abbreviation in preferred
                ]
                pref_is_live = any(g.state in _live for g in pref_games)
                if pref_is_live:
                    # Preferred team is live — show only their game(s)
                    all_games = pref_games
                # else: preferred team not live — keep full schedule so live
                # games from other teams are visible on the board

            with self._lock:
                self._current_games = all_games

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
