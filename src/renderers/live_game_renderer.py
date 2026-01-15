"""Live game renderer with animations."""
from typing import Optional
from .base_renderer import BaseRenderer
from .graphics import Colors, draw_baseball_diamond, draw_outs, draw_count
from .animations import (
    AnimationManager, ScoreChangeAnimation, RunnerAnimation,
    PulseAnimation, SlideAnimation
)
from ..models.game import LiveGameData, GameState


class LiveGameRenderer(BaseRenderer):
    """Renders live game with animated play-by-play."""

    def __init__(self, canvas, config):
        super().__init__(canvas, config)
        self.animation_manager = AnimationManager()
        self.last_game_state: Optional[LiveGameData] = None
        self.score_animations = {}
        self.live_pulse = PulseAnimation(duration=2.0)
        self.live_pulse.start()

    def render(self, game: LiveGameData):
        """Render live game display."""
        self.clear()

        # Check for score changes and trigger animations
        if self.last_game_state:
            self._check_for_animations(game)

        # Update animations
        self.animation_manager.update()

        # Render based on game state
        if game.state == GameState.PREVIEW or game.state == GameState.PREGAME:
            self._render_pregame(game)
        elif game.state == GameState.LIVE:
            self._render_live_game(game)
        elif game.state == GameState.FINAL:
            self._render_final(game)
        else:
            self._render_default(game)

        self.canvas.swap()
        self.last_game_state = game

    def _check_for_animations(self, game: LiveGameData):
        """Check for changes that should trigger animations."""
        if not self.config.animations.enabled:
            return

        last = self.last_game_state

        # Score change animations
        if game.away_team.score != last.away_team.score:
            anim = ScoreChangeAnimation(
                last.away_team.score,
                game.away_team.score,
                duration=2.0
            )
            self.score_animations['away'] = anim
            self.animation_manager.add(anim)

        if game.home_team.score != last.home_team.score:
            anim = ScoreChangeAnimation(
                last.home_team.score,
                game.home_team.score,
                duration=2.0
            )
            self.score_animations['home'] = anim
            self.animation_manager.add(anim)

    def _render_pregame(self, game: LiveGameData):
        """Render pre-game information."""
        # Team abbreviations
        away_color = Colors.WHITE
        home_color = Colors.WHITE

        self.canvas.draw_text(5, 8, game.away_team.abbreviation, *away_color)
        self.canvas.draw_text(5, 20, game.home_team.abbreviation, *home_color)

        # "vs" separator
        self.canvas.draw_text(35, 14, "vs", *Colors.FINAL_GRAY)

        # Game time
        time_str = game.start_time.strftime("%I:%M %p")
        self.canvas.draw_text(5, 35, time_str, *Colors.CYAN)

        # Probable pitchers if available
        if game.probable_pitcher_away:
            pitcher_text = game.probable_pitcher_away.split()[-1][:8]  # Last name
            self.canvas.draw_text(55, 8, f"P: {pitcher_text}", *Colors.YELLOW)

        if game.probable_pitcher_home:
            pitcher_text = game.probable_pitcher_home.split()[-1][:8]
            self.canvas.draw_text(55, 20, f"P: {pitcher_text}", *Colors.YELLOW)

    def _render_live_game(self, game: LiveGameData):
        """Render live game with full details and animations."""
        # Live indicator (pulsing)
        scale = self.live_pulse.get_scale()
        intensity = int(200 * scale)
        self.canvas.draw_circle(5, 5, 3, 0, intensity, 0, filled=True)
        self.canvas.draw_text(12, 8, "LIVE", 0, 200, 0)

        # Teams and scores
        y_away = 8
        y_home = 20

        # Away team
        self.canvas.draw_text(5, y_away, game.away_team.abbreviation, *Colors.WHITE)
        score_x = 40
        away_score = str(game.away_team.score)

        # Apply score animation if active
        away_color = Colors.WHITE
        if 'away' in self.score_animations:
            anim = self.score_animations['away']
            if anim.get_flash_state():
                intensity = anim.get_color_intensity()
                away_color = (
                    int(255 * intensity),
                    int(255 * intensity),
                    0
                )
            if anim.is_complete():
                del self.score_animations['away']

        self.canvas.draw_text(score_x, y_away, away_score, *away_color)

        # Home team
        self.canvas.draw_text(5, y_home, game.home_team.abbreviation, *Colors.WHITE)
        home_score = str(game.home_team.score)

        home_color = Colors.WHITE
        if 'home' in self.score_animations:
            anim = self.score_animations['home']
            if anim.get_flash_state():
                intensity = anim.get_color_intensity()
                home_color = (
                    int(255 * intensity),
                    int(255 * intensity),
                    0
                )
            if anim.is_complete():
                del self.score_animations['home']

        self.canvas.draw_text(score_x, y_home, home_score, *home_color)

        # Inning
        inning_text = f"{game.inning.half[0].upper()}{game.inning.num}"
        self.canvas.draw_text(60, 14, inning_text, *Colors.CYAN)

        # Baseball diamond with runners
        if self.config.modes.live_game.show_runners:
            runners = (
                game.runners.first is not None,
                game.runners.second is not None,
                game.runners.third is not None
            )
            draw_baseball_diamond(self.canvas, 85, 2, 16, runners, Colors.WHITE)

        # Count (balls, strikes, outs)
        if self.config.modes.live_game.show_pitch_count:
            draw_count(self.canvas, 75, 32, game.count.balls, game.count.strikes)

        # Outs
        if self.config.modes.live_game.show_outs:
            draw_outs(self.canvas, 105, 32, game.count.outs)

        # Current batter/pitcher info
        if game.current_batter:
            batter_name = game.current_batter.name.split()[-1][:10]  # Last name
            self.canvas.draw_text(5, 40, f"AB: {batter_name}", *Colors.YELLOW)
            if game.current_batter.avg:
                self.canvas.draw_text(5, 48, game.current_batter.avg, *Colors.WHITE)

        if game.current_pitcher:
            pitcher_name = game.current_pitcher.name.split()[-1][:10]
            self.canvas.draw_text(5, 56, f"P: {pitcher_name}", *Colors.ORANGE)
            if game.current_pitcher.era:
                self.canvas.draw_text(5, 64, game.current_pitcher.era, *Colors.WHITE)

        # Last play description (scrolling)
        if game.last_play:
            play_text = game.last_play.description[:40]
            play_color = Colors.RED if game.last_play.is_scoring_play else Colors.CYAN
            self.canvas.draw_text(60, 48, play_text[:20], *play_color)

    def _render_final(self, game: LiveGameData):
        """Render final score."""
        # FINAL indicator
        self.canvas.draw_text(5, 8, "FINAL", *Colors.RED)

        # Teams and scores
        y_away = 20
        y_home = 32

        self.canvas.draw_text(5, y_away, game.away_team.abbreviation, *Colors.WHITE)
        self.canvas.draw_text(40, y_away, str(game.away_team.score), *Colors.WHITE)

        self.canvas.draw_text(5, y_home, game.home_team.abbreviation, *Colors.WHITE)
        self.canvas.draw_text(40, y_home, str(game.home_team.score), *Colors.WHITE)

        # Highlight winner
        if game.away_team.is_winner:
            self.canvas.draw_rect(3, y_away - 9, 50, 11, *Colors.GREEN)
        elif game.home_team.is_winner:
            self.canvas.draw_rect(3, y_home - 9, 50, 11, *Colors.GREEN)

        # Line score (H-R-E)
        self.canvas.draw_text(60, y_away, f"{game.away_team.hits}-{game.away_team.errors}", *Colors.FINAL_GRAY)
        self.canvas.draw_text(60, y_home, f"{game.home_team.hits}-{game.home_team.errors}", *Colors.FINAL_GRAY)

    def _render_default(self, game: LiveGameData):
        """Default rendering for other game states."""
        self.canvas.draw_text(5, 8, game.state.value, *Colors.CYAN)
        self.canvas.draw_text(5, 20, f"{game.away_team.abbreviation} @ {game.home_team.abbreviation}", *Colors.WHITE)
