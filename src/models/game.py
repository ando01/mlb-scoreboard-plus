"""Game data models."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class GameState(str, Enum):
    """Game states."""
    PREVIEW = "Preview"
    PREGAME = "Pre-Game"
    WARMUP = "Warmup"
    LIVE = "Live"
    FINAL = "Final"
    POSTPONED = "Postponed"
    SUSPENDED = "Suspended"
    SCHEDULED = "Scheduled"      # Spring training / pre-season
    IN_PROGRESS = "In Progress"  # Alternate live state from API
    GAME_OVER = "Game Over"      # Alternate final state from API


# Maps raw MLB API detailedState / abstractGameState strings to GameState
_STATE_MAP: dict = {
    "scheduled": GameState.SCHEDULED,
    "pre-game": GameState.PREGAME,
    "pregame": GameState.PREGAME,
    "warmup": GameState.WARMUP,
    "preview": GameState.PREVIEW,
    "live": GameState.LIVE,
    "in progress": GameState.IN_PROGRESS,
    "manager challenge": GameState.LIVE,
    "review": GameState.LIVE,
    "game over": GameState.GAME_OVER,
    "final": GameState.FINAL,
    "completed early": GameState.FINAL,
    "postponed": GameState.POSTPONED,
    "suspended": GameState.SUSPENDED,
    "cancelled": GameState.POSTPONED,
    "delayed": GameState.PREVIEW,
    "delayed start": GameState.PREVIEW,
}


def parse_game_state(detail: str, abstract: str = "") -> GameState:
    """Map an MLB API state string to a GameState, with safe fallback."""
    for raw in (detail, abstract):
        key = raw.strip().lower()
        if key in _STATE_MAP:
            return _STATE_MAP[key]
    # Try the enum directly (handles values already matching enum members)
    for raw in (detail, abstract):
        try:
            return GameState(raw)
        except ValueError:
            pass
    return GameState.PREVIEW  # safe default


class BaseRunner(BaseModel):
    """Base runner information."""
    first: Optional[str] = None
    second: Optional[str] = None
    third: Optional[str] = None


class Count(BaseModel):
    """Pitch count."""
    balls: int = 0
    strikes: int = 0
    outs: int = 0


class PlayerStats(BaseModel):
    """Player statistics."""
    name: str
    avg: Optional[str] = None
    era: Optional[str] = None
    hits: Optional[int] = None
    at_bats: Optional[int] = None
    runs: Optional[int] = None
    rbi: Optional[int] = None
    hr: Optional[int] = None
    so: Optional[int] = None


class Team(BaseModel):
    """Team information."""
    id: int
    name: str
    abbreviation: str
    score: int = 0
    hits: int = 0
    errors: int = 0
    is_winner: bool = False


class Play(BaseModel):
    """Play-by-play event."""
    description: str
    event: str
    is_scoring_play: bool = False
    rbi: int = 0
    runners_movement: Optional[dict] = None


class Inning(BaseModel):
    """Current inning information."""
    num: int = 1
    ordinal: str = "1st"
    half: Literal["top", "bottom"] = "top"


class LiveGameData(BaseModel):
    """Live game data."""
    game_id: int
    state: GameState
    start_time: datetime
    inning: Inning = Field(default_factory=lambda: Inning())
    count: Count = Field(default_factory=Count)
    runners: BaseRunner = Field(default_factory=BaseRunner)
    home_team: Team
    away_team: Team
    current_batter: Optional[PlayerStats] = None
    current_pitcher: Optional[PlayerStats] = None
    last_play: Optional[Play] = None
    probable_pitcher_home: Optional[str] = None
    probable_pitcher_away: Optional[str] = None
    last_pitch_type: Optional[str] = None
    last_pitch_speed: Optional[float] = None
    pitch_count: Optional[int] = None  # Current pitch count
    show_pitch_result: bool = False  # Toggle between showing pitch count vs pitch result
    next_batters: List[str] = []  # Next 3 batters for the upcoming half-inning
    last_at_bat_result: Optional[str] = None  # Abbreviation of the last completed at-bat (e.g. "1B", "K", "BB")


class StandingsEntry(BaseModel):
    """Team standings entry."""
    team_name: str
    team_abbr: str
    wins: int
    losses: int
    pct: str
    gb: str
    division: str
