"""Game data fetcher service."""
import asyncio
from typing import List, Optional
from datetime import datetime
import logging
import os
from .mlb_client import MLBAPIClient
from .simulator import GameSimulator
from ..models.game import LiveGameData, StandingsEntry
from ..models.config import AppConfig

logger = logging.getLogger(__name__)


class DataFetcher:
    """Coordinates fetching and managing game data."""

    def __init__(self, config: AppConfig, simulate: bool = False):
        self.config = config
        self.simulate = simulate or os.getenv('SIMULATE_GAMES', 'false').lower() == 'true'
        self.client = MLBAPIClient()
        self.simulator = GameSimulator() if self.simulate else None
        self.current_games: List[LiveGameData] = []
        self.standings: List[StandingsEntry] = []
        self._running = False
        self._update_task: Optional[asyncio.Task] = None

        if self.simulate:
            logger.info("Running in SIMULATION mode - using fake game data")
            logger.info(f"Simulator has {len(self.simulator.games)} games at init")

    async def start(self):
        """Start the data fetcher."""
        logger.info("Starting data fetcher")
        self._running = True
        await self.client.__aenter__()
        logger.info("Creating update task...")
        self._update_task = asyncio.create_task(self._update_loop())
        logger.info(f"Update task created: {self._update_task}")
        # Give the task a moment to start
        await asyncio.sleep(0.1)

    async def stop(self):
        """Stop the data fetcher."""
        logger.info("Stopping data fetcher")
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        await self.client.__aexit__(None, None, None)

    async def _update_loop(self):
        """Main update loop."""
        try:
            logger.info("Update loop started")
        except Exception as e:
            logger.error(f"Error even logging start: {e}")

        while self._running:
            try:
                logger.info("Calling _fetch_all_data()")
                await self._fetch_all_data()
                logger.info("_fetch_all_data() completed")
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                logger.info("Update loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

    async def _fetch_all_data(self):
        """Fetch all required data."""
        logger.info("_fetch_all_data called")
        tasks = [
            self._fetch_games(),
        ]

        if self.config.modes.standings.enabled:
            tasks.append(self._fetch_standings())

        logger.info(f"Gathering {len(tasks)} tasks")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Gather completed with results: {results}")

    async def _fetch_games(self):
        """Fetch today's games."""
        logger.info(f"_fetch_games called, simulate={self.simulate}")
        try:
            # Use simulator if enabled
            if self.simulate:
                logger.info(f"About to call simulator.get_games(), simulator={self.simulator}")
                self.current_games = self.simulator.get_games()
                logger.info(f"Simulated {len(self.current_games)} games")
                if len(self.current_games) == 0:
                    logger.error("Simulator returned 0 games - check simulator initialization")
                else:
                    for game in self.current_games:
                        logger.info(f"  Game: {game.away_team.abbreviation} @ {game.home_team.abbreviation} - {game.state}")
                return

            # Get game IDs
            if self.config.teams.display_all:
                game_ids = await self.client.get_todays_games()
            else:
                # Get games for preferred teams
                game_ids = []
                for team in self.config.teams.preferred_teams:
                    team_games = await self.client.get_todays_games()
                    game_ids.extend(team_games)
                game_ids = list(set(game_ids))  # Remove duplicates

            # Fetch game data concurrently
            if game_ids:
                games = await asyncio.gather(
                    *[self.client.get_game_data(gid) for gid in game_ids],
                    return_exceptions=True
                )
                self.current_games = [g for g in games if isinstance(g, LiveGameData)]
                logger.debug(f"Fetched {len(self.current_games)} games")
            else:
                self.current_games = []
                logger.debug("No games today")

        except Exception as e:
            logger.error(f"Error fetching games: {e}", exc_info=True)

    async def _fetch_standings(self):
        """Fetch standings data."""
        try:
            # Use simulator if enabled
            if self.simulate:
                self.standings = self.simulator.get_standings()
                logger.debug(f"Simulated standings for {len(self.standings)} teams")
                return

            all_standings = []
            for division in self.config.modes.standings.divisions:
                standings = await self.client.get_standings(division)
                all_standings.extend(standings)
            self.standings = all_standings
            logger.debug(f"Fetched standings for {len(all_standings)} teams")
        except Exception as e:
            logger.error(f"Error fetching standings: {e}", exc_info=True)

    def get_games(self) -> List[LiveGameData]:
        """Get current games."""
        return self.current_games

    def get_standings(self) -> List[StandingsEntry]:
        """Get current standings."""
        return self.standings

    def get_live_games(self) -> List[LiveGameData]:
        """Get only live games."""
        from ..models.game import GameState
        return [g for g in self.current_games if g.state == GameState.LIVE]

    def get_favorite_game(self) -> Optional[LiveGameData]:
        """Get the favorite team's game if available."""
        fav = self.config.teams.favorite
        for game in self.current_games:
            if game.home_team.abbreviation == fav or game.away_team.abbreviation == fav:
                return game
        return None

    def set_simulation_mode(self, enabled: bool):
        """Enable or disable simulation mode at runtime."""
        if enabled == self.simulate:
            return  # No change needed

        self.simulate = enabled
        if enabled:
            if not self.simulator:
                self.simulator = GameSimulator()
            logger.info("Switched to SIMULATION mode")
        else:
            logger.info("Switched to LIVE mode")

        # Clear current games to force refresh
        self.current_games = []
        self.standings = []
