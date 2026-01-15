"""Game data fetcher service."""
import asyncio
from typing import List, Optional
from datetime import datetime
import logging
from .mlb_client import MLBAPIClient
from ..models.game import LiveGameData, StandingsEntry
from ..models.config import AppConfig

logger = logging.getLogger(__name__)


class DataFetcher:
    """Coordinates fetching and managing game data."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.client = MLBAPIClient()
        self.current_games: List[LiveGameData] = []
        self.standings: List[StandingsEntry] = []
        self._running = False
        self._update_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the data fetcher."""
        logger.info("Starting data fetcher")
        self._running = True
        await self.client.__aenter__()
        self._update_task = asyncio.create_task(self._update_loop())

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
        while self._running:
            try:
                await self._fetch_all_data()
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

    async def _fetch_all_data(self):
        """Fetch all required data."""
        tasks = [
            self._fetch_games(),
        ]

        if self.config.modes.standings.enabled:
            tasks.append(self._fetch_standings())

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_games(self):
        """Fetch today's games."""
        try:
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
