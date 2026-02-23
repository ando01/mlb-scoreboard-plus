"""MLB Stats API client.

All HTTP calls are synchronous (requests library).  The client is called
from DataFetcher's background thread, which is completely separate from
the asyncio event loop.  This avoids the event-loop starvation caused by
the LED-matrix canvas.swap() / SwapOnVSync() blocking the event loop.
"""
import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from ..models.game import (
    LiveGameData, GameState, parse_game_state, Team, Inning, Count,
    BaseRunner, Play, PlayerStats, StandingsEntry
)

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15  # seconds


def _get_json(url: str, params: Optional[dict] = None) -> dict:
    """Synchronous JSON fetch with timeout."""
    resp = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


class MLBAPIClient:
    """MLB Stats API client (synchronous, runs in a background thread)."""

    def __init__(self, base_url: str = "https://statsapi.mlb.com"):
        self.base_url = base_url
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._cache_duration = timedelta(seconds=10)

    # No-op async context manager kept for call-site compatibility.
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

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

    def get_todays_games(self) -> List[int]:
        """Return today's game PKs across all game types (sync)."""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_key = f"today_games_{today}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"{self.base_url}/api/v1/schedule"
            params = {
                "sportId": 1,
                "date": today,
                "gameType": "E,S,R,F,D,L,W,C",  # all types inc. spring training
            }
            data = _get_json(url, params)
            game_ids = [
                game["gamePk"]
                for date_entry in data.get("dates", [])
                for game in date_entry.get("games", [])
                if game.get("gamePk")
            ]
            logger.info(f"Schedule {today}: {len(game_ids)} games {game_ids}")
            self._set_cache(cache_key, game_ids)
            return game_ids
        except Exception as e:
            logger.error(f"Schedule fetch failed: {e}", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Game feed
    # ------------------------------------------------------------------

    def get_game_data(self, game_id: int) -> LiveGameData:
        """Fetch and parse a single game's live feed (sync)."""
        cache_key = f"game_{game_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        url = f"{self.base_url}/api/v1.1/game/{game_id}/feed/live"
        game_data = _get_json(url)
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

        # ----------------------------------------------------------------
        # Player lookup helpers
        # ----------------------------------------------------------------
        # gameData.players is keyed "ID{id}" and contains boxscoreName /
        # fullName for every player on both rosters — the canonical source
        # used by the reference MLB-LED-Scoreboard project.
        gd_players = game_info.get("players", {})  # {"ID123": {"boxscoreName": ..., ...}}

        def player_name(player_obj: dict) -> str:
            """Return display name, preferring gameData.players lookup."""
            pid = player_obj.get("id")
            if pid:
                entry = gd_players.get(f"ID{pid}", {})
                name = entry.get("boxscoreName") or entry.get("fullName")
                if name:
                    return name
            return player_obj.get("fullName") or player_obj.get("name") or "Unknown"

        # Build player-id → boxscore entry for stat lookups
        boxscore = live_data.get("boxscore", {})
        bs_players: Dict[int, dict] = {}
        for side in ("home", "away"):
            for pdata in boxscore.get("teams", {}).get(side, {}).get("players", {}).values():
                pid = pdata.get("person", {}).get("id")
                if pid:
                    bs_players[pid] = pdata

        # ----------------------------------------------------------------
        # Runners
        # ----------------------------------------------------------------
        offense = line_score.get("offense", {})
        defense = line_score.get("defense", {})
        runners = BaseRunner(
            first=player_name(offense["first"]) if offense.get("first") else None,
            second=player_name(offense["second"]) if offense.get("second") else None,
            third=player_name(offense["third"]) if offense.get("third") else None,
        )

        # ----------------------------------------------------------------
        # Current batter — linescore.offense.batter
        # ----------------------------------------------------------------
        current_batter = None
        if offense.get("batter"):
            b = offense["batter"]
            bstats = bs_players.get(b.get("id"), {})
            avg = bstats.get("seasonStats", {}).get("batting", {}).get("avg", ".000")
            current_batter = PlayerStats(
                name=player_name(b),
                avg=str(avg),
            )

        # ----------------------------------------------------------------
        # Current pitcher — linescore.defense.pitcher
        # ----------------------------------------------------------------
        current_pitcher = None
        if defense.get("pitcher"):
            p = defense["pitcher"]
            pid = p.get("id")
            pstats = bs_players.get(pid, {})
            era = pstats.get("seasonStats", {}).get("pitching", {}).get("era", "0.00")
            current_pitcher = PlayerStats(
                name=player_name(p),
                era=str(era),
            )

        # ----------------------------------------------------------------
        # Pitch data — currentPlay.playEvents (mirrors reference approach)
        # ----------------------------------------------------------------
        last_pitch_type: Optional[str] = None
        last_pitch_speed: Optional[float] = None
        pitch_count: Optional[int] = None
        show_pitch_result: bool = False

        current_play = live_data.get("plays", {}).get("currentPlay", {})
        if current_play:
            play_events = current_play.get("playEvents", [])
            # Find the last pitch event in the current at-bat
            for event in reversed(play_events):
                if event.get("isPitch", False):
                    last_pitch_speed = event.get("pitchData", {}).get("startSpeed")
                    details = event.get("details", {})
                    last_pitch_type = details.get("type", {}).get("description")
                    show_pitch_result = True
                    break

        # Total pitch count for the current pitcher (game stats, not season stats)
        if current_pitcher and defense.get("pitcher"):
            pid = defense["pitcher"].get("id")
            if pid:
                pentry = bs_players.get(pid, {})
                np = pentry.get("stats", {}).get("pitching", {}).get("numberOfPitches")
                if np is not None:
                    pitch_count = int(np)

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
            last_pitch_type=last_pitch_type,
            last_pitch_speed=last_pitch_speed,
            pitch_count=pitch_count,
            show_pitch_result=show_pitch_result,
        )

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    def get_standings(self, division: str) -> List[StandingsEntry]:
        """Fetch division standings (sync)."""
        cache_key = f"standings_{division}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        entries: List[StandingsEntry] = []
        try:
            year = datetime.now().year
            url = f"{self.base_url}/api/v1/standings"
            params = {"leagueId": "103,104", "season": year, "hydrate": "team"}
            data = _get_json(url, params)

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
