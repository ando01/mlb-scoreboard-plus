"""MLB Stats API client — fully async via aiohttp (no statsapi library)."""
import aiohttp
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from ..models.game import (
    LiveGameData, GameState, parse_game_state, Team, Inning, Count,
    BaseRunner, Play, PlayerStats, StandingsEntry
)

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=15)


class MLBAPIClient:
    """Async MLB Stats API client."""

    def __init__(self, base_url: str = "https://statsapi.mlb.com"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_duration = timedelta(seconds=10)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_duration:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = (data, datetime.now())

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------

    async def _fetch_schedule(self, date: str, game_type: str = "E,S,R,F,D,L,W,C") -> List[int]:
        """Fetch game PKs from /api/v1/schedule.

        gameType codes: S=Spring Training, R=Regular Season, E=Exhibition,
        F=Wild Card, D=Division Series, L=LCS, W=World Series, C=Championship.
        Passing all types means one call covers spring training and regular
        season without any fallback logic.
        """
        try:
            url = f"{self.base_url}/api/v1/schedule"
            params = {"sportId": 1, "date": date, "gameType": game_type}
            async with self.session.get(url, params=params, timeout=_TIMEOUT) as resp:
                data = await resp.json(content_type=None)
            game_ids = [
                game["gamePk"]
                for date_entry in data.get("dates", [])
                for game in date_entry.get("games", [])
                if game.get("gamePk")
            ]
            logger.info(f"Schedule date={date} gameType={game_type}: {len(game_ids)} games {game_ids}")
            return game_ids
        except Exception as e:
            logger.error(f"Schedule fetch failed (date={date}): {e}", exc_info=True)
            return []

    async def get_todays_games(self, team_id: Optional[int] = None) -> List[int]:
        """Get today's game PKs across all game types (regular season, spring training, playoffs)."""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = f"today_games_{today}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        game_ids = await self._fetch_schedule(date=today)
        self._set_cache(cache_key, game_ids)
        return game_ids

    # ------------------------------------------------------------------
    # Game feed
    # ------------------------------------------------------------------

    async def get_game_data(self, game_id: int) -> LiveGameData:
        """Fetch and parse a single game's live feed."""
        cache_key = f"game_{game_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        url = f"{self.base_url}/api/v1.1/game/{game_id}/feed/live"
        async with self.session.get(url, timeout=_TIMEOUT) as resp:
            game_data = await resp.json(content_type=None)

        parsed = self._parse_game_data(game_data)
        self._set_cache(cache_key, parsed)
        return parsed

    def _parse_game_data(self, game_data: dict) -> LiveGameData:
        """Parse raw game feed into LiveGameData."""
        game_pk = game_data["gamePk"]
        game_info = game_data.get("gameData", {})
        live_data = game_data.get("liveData", {})

        # Game state
        status = game_info.get("status", {})
        abstract_state = status.get("abstractGameState", "Preview")
        detailed_state = status.get("detailedState", abstract_state)
        state = parse_game_state(detailed_state, abstract_state)

        # Start time
        try:
            start_time = datetime.fromisoformat(
                game_info.get("datetime", {}).get("dateTime", "").replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            start_time = datetime.now()

        # Teams
        teams_data = game_info.get("teams", {})
        home = teams_data.get("home", {})
        away = teams_data.get("away", {})

        line_score = live_data.get("linescore", {})
        home_score = line_score.get("teams", {}).get("home", {})
        away_score = line_score.get("teams", {}).get("away", {})

        home_team = Team(
            id=home.get("id", 0),
            name=home.get("name", "Unknown"),
            abbreviation=home.get("abbreviation", "UNK"),
            score=home_score.get("runs", 0),
            hits=home_score.get("hits", 0),
            errors=home_score.get("errors", 0),
            is_winner=line_score.get("isTopInning", False) is False,
        )
        away_team = Team(
            id=away.get("id", 0),
            name=away.get("name", "Unknown"),
            abbreviation=away.get("abbreviation", "UNK"),
            score=away_score.get("runs", 0),
            hits=away_score.get("hits", 0),
            errors=away_score.get("errors", 0),
            is_winner=line_score.get("isTopInning", False) is True,
        )

        # Inning
        inning_num = line_score.get("currentInning", 1)
        inning_half = "top" if line_score.get("isTopInning", True) else "bottom"
        inning = Inning(
            num=inning_num,
            ordinal=line_score.get("currentInningOrdinal", f"{inning_num}th"),
            half=inning_half,
        )

        # Count
        count = Count(
            balls=line_score.get("balls", 0),
            strikes=line_score.get("strikes", 0),
            outs=line_score.get("outs", 0),
        )

        # Runners
        offense = line_score.get("offense", {})
        runners = BaseRunner(
            first=offense.get("first", {}).get("fullName") if offense.get("first") else None,
            second=offense.get("second", {}).get("fullName") if offense.get("second") else None,
            third=offense.get("third", {}).get("fullName") if offense.get("third") else None,
        )

        # Current players
        current_batter = None
        if offense.get("batter"):
            b = offense["batter"]
            current_batter = PlayerStats(
                name=b.get("fullName", "Unknown"),
                avg=str(b.get("avg", ".000")),
            )

        current_pitcher = None
        if offense.get("pitcher"):
            p = offense["pitcher"]
            current_pitcher = PlayerStats(
                name=p.get("fullName", "Unknown"),
                era=str(p.get("era", "0.00")),
            )

        # Last play
        last_play = None
        plays = live_data.get("plays", {}).get("allPlays", [])
        if plays:
            last = plays[-1]
            result = last.get("result", {})
            last_play = Play(
                description=result.get("description", ""),
                event=result.get("event", ""),
                is_scoring_play=result.get("isScoringPlay", False),
                rbi=result.get("rbi", 0),
            )

        # Probable pitchers (preview / pregame / scheduled)
        prob_home = None
        prob_away = None
        preview_states = {GameState.PREVIEW, GameState.PREGAME, GameState.SCHEDULED}
        if state in preview_states:
            prob_pitchers = game_info.get("probablePitchers", {})
            if prob_pitchers.get("home"):
                prob_home = prob_pitchers["home"].get("fullName")
            if prob_pitchers.get("away"):
                prob_away = prob_pitchers["away"].get("fullName")

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
            probable_pitcher_away=prob_away,
        )

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    async def get_standings(self, division: str) -> List[StandingsEntry]:
        """Fetch division standings from /api/v1/standings."""
        cache_key = f"standings_{division}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        entries: List[StandingsEntry] = []
        try:
            year = datetime.now().year
            url = f"{self.base_url}/api/v1/standings"
            params = {"leagueId": "103,104", "season": year, "hydrate": "team"}
            async with self.session.get(url, params=params, timeout=_TIMEOUT) as resp:
                data = await resp.json(content_type=None)

            for record in data.get("records", []):
                div_name = record.get("division", {}).get("name", "")
                if division.lower() not in div_name.lower():
                    continue
                for tr in record.get("teamRecords", []):
                    team = tr.get("team", {})
                    abbr = (
                        team.get("abbreviation")
                        or team.get("clubName", "???")
                    )
                    entries.append(StandingsEntry(
                        team_name=team.get("name", ""),
                        team_abbr=abbr,
                        wins=tr.get("wins", 0),
                        losses=tr.get("losses", 0),
                        pct=tr.get("winningPercentage", ".000"),
                        gb=str(tr.get("gamesBack", "-")),
                        division=div_name,
                    ))
        except Exception as e:
            logger.error(f"Standings fetch failed for '{division}': {e}", exc_info=True)

        self._set_cache(cache_key, entries)
        return entries
