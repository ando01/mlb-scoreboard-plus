"""Configuration models using Pydantic."""
from pydantic import BaseModel, Field
from typing import List, Literal


class DisplayConfig(BaseModel):
    """Display settings."""
    brightness: int = Field(default=60, ge=0, le=100)
    rotation_enabled: bool = True
    rotation_interval: int = Field(default=15, ge=5)
    default_mode: str = "live_game"
    matrix_enabled: bool = True


class TeamsConfig(BaseModel):
    """Team preferences."""
    favorite: str = "NYY"
    display_all: bool = True
    preferred_teams: List[str] = Field(default_factory=lambda: ["NYY"])


class LiveGameModeConfig(BaseModel):
    """Live game display settings."""
    enabled: bool = True
    show_pitch_count: bool = True
    show_runners: bool = True
    show_outs: bool = True
    animate_plays: bool = True


class DetailedStatsModeConfig(BaseModel):
    """Detailed stats display settings."""
    enabled: bool = True
    show_batter_stats: bool = True
    show_pitcher_stats: bool = True


class StandingsModeConfig(BaseModel):
    """Standings display settings."""
    enabled: bool = True
    divisions: List[str] = Field(default_factory=lambda: ["AL East"])


class ModesConfig(BaseModel):
    """Display mode configurations."""
    live_game: LiveGameModeConfig = Field(default_factory=LiveGameModeConfig)
    detailed_stats: DetailedStatsModeConfig = Field(default_factory=DetailedStatsModeConfig)
    standings: StandingsModeConfig = Field(default_factory=StandingsModeConfig)


class AnimationsConfig(BaseModel):
    """Animation settings."""
    enabled: bool = True
    transition_speed: Literal["slow", "normal", "fast"] = "normal"
    celebrate_home_runs: bool = True
    celebrate_strikeouts: bool = True


class AppConfig(BaseModel):
    """Main application configuration."""
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    teams: TeamsConfig = Field(default_factory=TeamsConfig)
    modes: ModesConfig = Field(default_factory=ModesConfig)
    animations: AnimationsConfig = Field(default_factory=AnimationsConfig)
