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

# Maps MLB API result.event strings (lower-cased) to display abbreviations
_AT_BAT_ABBREVS: dict = {
    "single": "1B",
    "double": "2B",
    "triple": "3B",
    "home run": "HR",
    "walk": "BB",
    "intent walk": "IBB",
    "hit by pitch": "HBP",
    "strikeout": "K",
    "strikeout - double play": "KDP",
    "grounded into double play": "GDP",
    "double play": "DP",
    "triple play": "TP",
    "sac fly": "SF",
    "sac fly double play": "SFDP",
    "sac bunt": "SH",
    "fielders choice": "FC",
    "fielders choice out": "FC",
    "field error": "E",
    "error": "E",
    "groundout": "GO",
    "flyout": "FO",
    "pop out": "PO",
    "lineout": "LO",
    "forceout": "FO",
    "bunt groundout": "GO",
    "bunt pop out": "PO",
    "runner out": "OUT",
}


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
        self._game_cache_ttl = timedelta(seconds=8)    # live game data
        self._schedule_cache_ttl = timedelta(seconds=60)  # game IDs rarely change

    # No-op async context manager kept for call-site compatibility.
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _get_cached(self, key: str, ttl: Optional[timedelta] = None) -> Optional[Any]:
        if key in self._cache:
            data, timestamp = self._cache[key]
            effective_ttl = ttl if ttl is not None else self._game_cache_ttl
            if datetime.now() - timestamp < effective_ttl:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = (data, datetime.now())

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------

    def get_schedule_with_details(self, date: str) -> List[LiveGameData]:
        """Fetch today's full schedule as lightweight LiveGameData objects.

        Uses linescore+team hydration (no probablePitchers — that was the
        cause of the API returning fewer games).  Gives us team abbreviations,
        score, current inning, and half-inning for the schedule ticker.
        Cached for 30 seconds.
        """
        cache_key = f"schedule_details_{date}"
        cached = self._get_cached(cache_key, ttl=timedelta(seconds=30))
        if cached is not None:
            return cached

        try:
            url = f"{self.base_url}/api/v1/schedule"
            params = {
                "sportId": 1,
                "date": date,
                "gameType": "E,S,R,F,D,L,W,C",
                "hydrate": "linescore,team",  # probablePitchers omitted — causes API to return fewer games
            }
            data = _get_json(url, params)
            games = []
            for date_entry in data.get("dates", []):
                for g in date_entry.get("games", []):
                    parsed = self._parse_schedule_game(g)
                    if parsed:
                        games.append(parsed)
            logger.info(f"Schedule {date}: {len(games)} games (lightweight)")
            self._set_cache(cache_key, games)
            return games
        except Exception as e:
            logger.error(f"Schedule fetch failed: {e}", exc_info=True)
            return []

    def _parse_schedule_game(self, g: dict) -> Optional[LiveGameData]:
        """Parse a schedule-endpoint game object into a basic LiveGameData."""
        try:
            game_pk = g.get("gamePk")
            if not game_pk:
                return None

            status = g.get("status", {})
            state = parse_game_state(
                status.get("detailedState", ""),
                status.get("abstractGameState", "Preview"),
            )

            try:
                start_time = datetime.fromisoformat(
                    g.get("gameDate", "").replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                start_time = datetime.now()

            teams_data = g.get("teams", {})
            home_data = teams_data.get("home", {})
            away_data = teams_data.get("away", {})
            home_info = home_data.get("team", {})
            away_info = away_data.get("team", {})

            home_team = Team(
                id=home_info.get("id", 0),
                name=home_info.get("name", "Unknown"),
                abbreviation=home_info.get("abbreviation", "UNK"),
                score=home_data.get("score", 0),
                hits=0, errors=0,
            )
            away_team = Team(
                id=away_info.get("id", 0),
                name=away_info.get("name", "Unknown"),
                abbreviation=away_info.get("abbreviation", "UNK"),
                score=away_data.get("score", 0),
                hits=0, errors=0,
            )

            ls = g.get("linescore", {})
            inning_num = ls.get("currentInning", 1)
            inning = Inning(
                num=inning_num,
                ordinal=ls.get("currentInningOrdinal", f"{inning_num}th"),
                half="top" if ls.get("isTopInning", True) else "bottom",
            )
            count = Count(
                balls=ls.get("balls", 0),
                strikes=ls.get("strikes", 0),
                outs=ls.get("outs", 0),
            )

            prob = g.get("probablePitchers", {})
            return LiveGameData(
                game_id=game_pk,
                state=state,
                start_time=start_time,
                inning=inning,
                count=count,
                runners=BaseRunner(),
                home_team=home_team,
                away_team=away_team,
                probable_pitcher_home=prob.get("home", {}).get("fullName"),
                probable_pitcher_away=prob.get("away", {}).get("fullName"),
            )
        except Exception as e:
            logger.error(f"Error parsing schedule game {g.get('gamePk')}: {e}")
            return None

    # ------------------------------------------------------------------
    # Game feed
    # ------------------------------------------------------------------

    def get_game_data(self, game_id: int) -> LiveGameData:
        """Fetch and parse a single game's live feed (sync, no cache).

        Called only for the one game currently on the board, so caching
        would just introduce unnecessary lag.
        """
        url = f"{self.base_url}/api/v1.1/game/{game_id}/feed/live"
        game_data = _get_json(url)
        return self._parse_game_data(game_data)

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
            game_batting = bstats.get("stats", {}).get("batting", {})
            current_batter = PlayerStats(
                name=player_name(b),
                avg=str(avg),
                hits=game_batting.get("hits"),
                at_bats=game_batting.get("atBats"),
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
        last_at_bat_result: Optional[str] = None

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

            # Show at-bat result only when the current play is complete.
            # Clears automatically when the next batter's at-bat begins.
            if current_play.get("about", {}).get("isComplete", False):
                event_str = current_play.get("result", {}).get("event", "")
                if event_str:
                    last_at_bat_result = _AT_BAT_ABBREVS.get(
                        event_str.lower(), event_str[:4].upper()
                    )

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

        # ----------------------------------------------------------------
        # Next batters — populated when outs == 3 (end of half-inning)
        # ----------------------------------------------------------------
        next_batters: list = []
        _live_states = {GameState.LIVE, GameState.IN_PROGRESS}
        if count.outs >= 3 and state in _live_states:
            is_top = line_score.get("isTopInning", True)
            # The team batting NEXT is the opposite of whoever is batting now.
            # Top of inning = away batting → home bats next (bottom).
            # Bottom of inning = home batting → away bats next (top).
            next_side = "home" if is_top else "away"
            batting_order = (
                boxscore.get("teams", {})
                        .get(next_side, {})
                        .get("battingOrder", [])
            )
            if batting_order:
                # Find last at-bat from the upcoming team by scanning allPlays
                # in reverse — tells us where they are in the batting order.
                expected_half = "bottom" if next_side == "home" else "top"
                batting_set = set(batting_order)
                all_plays = live_data.get("plays", {}).get("allPlays", [])
                last_batter_id = None
                for play in reversed(all_plays):
                    if play.get("about", {}).get("halfInning") == expected_half:
                        bid = play.get("matchup", {}).get("batter", {}).get("id")
                        if bid and bid in batting_set:
                            last_batter_id = bid
                            break

                if last_batter_id and last_batter_id in batting_order:
                    pos = batting_order.index(last_batter_id)
                    n = len(batting_order)
                    next_ids = [batting_order[(pos + 1 + i) % n] for i in range(3)]
                else:
                    # Can't determine position — start from top of order
                    next_ids = batting_order[:3]

                for pid in next_ids:
                    entry = gd_players.get(f"ID{pid}", {})
                    name = entry.get("boxscoreName") or entry.get("fullName") or ""
                    if name:
                        next_batters.append(name)

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
            next_batters=next_batters,
            last_at_bat_result=last_at_bat_result,
        )

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    def get_standings(self, division: str) -> List[StandingsEntry]:
        """Fetch division standings (sync)."""
        cache_key = f"standings_{division}"
        cached = self._get_cached(cache_key, ttl=self._schedule_cache_ttl)
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
