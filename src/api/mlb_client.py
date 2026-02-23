"""MLB Stats API client with async support."""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import statsapi
from ..models.game import (
    LiveGameData, GameState, Team, Inning, Count,
    BaseRunner, Play, PlayerStats, StandingsEntry
)


class MLBAPIClient:
    """Async MLB Stats API client."""

    def __init__(self, base_url: str = "https://statsapi.mlb.com"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_duration = timedelta(seconds=10)

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if still valid."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_duration:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        """Cache data with timestamp."""
        self._cache[key] = (data, datetime.now())

    async def get_todays_games(self, team_id: Optional[int] = None) -> List[int]:
        """Get today's game IDs, including spring training fallback."""
        cache_key = f"today_games_{team_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        loop = asyncio.get_event_loop()

        # Try regular season first (sportId=1)
        games = await loop.run_in_executor(
            None,
            lambda: statsapi.schedule(team=team_id) if team_id else statsapi.schedule()
        )

        # Fall back to spring training (sportId=17) if no regular season games found
        if not games:
            games = await loop.run_in_executor(
                None,
                lambda: statsapi.schedule(team=team_id, sportId=17) if team_id else statsapi.schedule(sportId=17)
            )

        game_ids = [g['game_id'] for g in games if g.get('game_id')]
        self._set_cache(cache_key, game_ids)
        return game_ids

    def _parse_game_data(self, game_data: dict) -> LiveGameData:
        """Parse raw game data into LiveGameData model."""
        game_pk = game_data['gamePk']
        game_info = game_data.get('gameData', {})
        live_data = game_data.get('liveData', {})

        # Game state
        status = game_info.get('status', {})
        abstract_state = status.get('abstractGameState', 'Preview')
        state = GameState(status.get('detailedState', abstract_state))

        # Start time
        start_time = datetime.fromisoformat(
            game_info.get('datetime', {}).get('dateTime', '').replace('Z', '+00:00')
        )

        # Teams
        teams_data = game_info.get('teams', {})
        home = teams_data.get('home', {})
        away = teams_data.get('away', {})

        line_score = live_data.get('linescore', {})
        home_score = line_score.get('teams', {}).get('home', {})
        away_score = line_score.get('teams', {}).get('away', {})

        home_team = Team(
            id=home.get('id', 0),
            name=home.get('name', 'Unknown'),
            abbreviation=home.get('abbreviation', 'UNK'),
            score=home_score.get('runs', 0),
            hits=home_score.get('hits', 0),
            errors=home_score.get('errors', 0),
            is_winner=line_score.get('isTopInning', False) == False
        )

        away_team = Team(
            id=away.get('id', 0),
            name=away.get('name', 'Unknown'),
            abbreviation=away.get('abbreviation', 'UNK'),
            score=away_score.get('runs', 0),
            hits=away_score.get('hits', 0),
            errors=away_score.get('errors', 0),
            is_winner=line_score.get('isTopInning', False) == True
        )

        # Inning
        inning_num = line_score.get('currentInning', 1)
        inning_half = "top" if line_score.get('isTopInning', True) else "bottom"
        inning = Inning(
            num=inning_num,
            ordinal=line_score.get('currentInningOrdinal', f'{inning_num}th'),
            half=inning_half
        )

        # Count
        count = Count(
            balls=line_score.get('balls', 0),
            strikes=line_score.get('strikes', 0),
            outs=line_score.get('outs', 0)
        )

        # Runners
        offense = line_score.get('offense', {})
        runners = BaseRunner(
            first=offense.get('first', {}).get('fullName') if offense.get('first') else None,
            second=offense.get('second', {}).get('fullName') if offense.get('second') else None,
            third=offense.get('third', {}).get('fullName') if offense.get('third') else None
        )

        # Current players
        current_batter = None
        if offense.get('batter'):
            batter = offense['batter']
            current_batter = PlayerStats(
                name=batter.get('fullName', 'Unknown'),
                avg=str(batter.get('avg', '.000'))
            )

        current_pitcher = None
        if offense.get('pitcher'):
            pitcher = offense['pitcher']
            current_pitcher = PlayerStats(
                name=pitcher.get('fullName', 'Unknown'),
                era=str(pitcher.get('era', '0.00'))
            )

        # Last play
        last_play = None
        plays = live_data.get('plays', {}).get('allPlays', [])
        if plays:
            last = plays[-1]
            result = last.get('result', {})
            last_play = Play(
                description=result.get('description', ''),
                event=result.get('event', ''),
                is_scoring_play=result.get('isScoringPlay', False),
                rbi=result.get('rbi', 0)
            )

        # Probable pitchers (for preview games)
        prob_home = None
        prob_away = None
        if state in [GameState.PREVIEW, GameState.PREGAME]:
            prob_pitchers = game_info.get('probablePitchers', {})
            if prob_pitchers.get('home'):
                prob_home = prob_pitchers['home'].get('fullName')
            if prob_pitchers.get('away'):
                prob_away = prob_pitchers['away'].get('fullName')

        return LiveGameData(
            game_id=game_pk,
            state=state,
            start_time=start_time,
            inning=inning,
            count=count,
            runners=runners,
            home_team=home_team,
            away_team=away_team,
            current_batter=current_batter,
            current_pitcher=current_pitcher,
            last_play=last_play,
            probable_pitcher_home=prob_home,
            probable_pitcher_away=prob_away
        )

    async def get_game_data(self, game_id: int) -> LiveGameData:
        """Get live game data."""
        cache_key = f"game_{game_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Fetch game data using statsapi
        loop = asyncio.get_event_loop()
        game_data = await loop.run_in_executor(
            None,
            lambda: statsapi.get('game', {'gamePk': game_id})
        )

        parsed = self._parse_game_data(game_data)
        self._set_cache(cache_key, parsed)
        return parsed

    async def get_standings(self, division: str) -> List[StandingsEntry]:
        """Get division standings."""
        cache_key = f"standings_{division}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        loop = asyncio.get_event_loop()
        standings_data = await loop.run_in_executor(
            None,
            lambda: statsapi.standings_data(leagueId="103,104")
        )

        entries = []
        for div_data in standings_data.values():
            if division.lower() in div_data.get('div_name', '').lower():
                for team in div_data.get('teams', []):
                    entries.append(StandingsEntry(
                        team_name=team.get('name', ''),
                        team_abbr=team.get('team_abbr', ''),
                        wins=team.get('w', 0),
                        losses=team.get('l', 0),
                        pct=team.get('pct', '.000'),
                        gb=team.get('gb', '-'),
                        division=div_data.get('div_name', '')
                    ))

        self._set_cache(cache_key, entries)
        return entries
