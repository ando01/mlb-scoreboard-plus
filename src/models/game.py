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


class StandingsEntry(BaseModel):
    """Team standings entry."""
    team_name: str
    team_abbr: str
    wins: int
    losses: int
    pct: str
    gb: str
    division: str
