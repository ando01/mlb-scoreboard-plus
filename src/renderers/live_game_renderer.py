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
        """Render live game with full details - matches original mlb-led-scoreboard style."""

        # TOP SECTION: Team name bars with scores (like original)
        # Away team bar (top) - blue background
        self.canvas.draw_rect(0, 0, 128, 13, 0, 50, 150, filled=True)
        self.canvas.draw_text(2, 10, game.away_team.abbreviation, *Colors.WHITE)

        # Away score (right side of blue bar)
        away_score = str(game.away_team.score).zfill(2)  # Pad with zero like "04"
        score_x = 128 - (len(away_score) * 7 + 5)

        away_color = Colors.WHITE
        if 'away' in self.score_animations:
            anim = self.score_animations['away']
            if anim.get_flash_state():
                away_color = Colors.YELLOW
            if anim.is_complete():
                del self.score_animations['away']

        self.canvas.draw_text(score_x, 10, away_score, *away_color)

        # Home team bar - magenta/purple background
        self.canvas.draw_rect(0, 14, 128, 13, 150, 0, 100, filled=True)
        self.canvas.draw_text(2, 24, game.home_team.abbreviation, *Colors.WHITE)

        # Home score
        home_score = str(game.home_team.score).zfill(2)

        home_color = Colors.WHITE
        if 'home' in self.score_animations:
            anim = self.score_animations['home']
            if anim.get_flash_state():
                home_color = Colors.YELLOW
            if anim.is_complete():
                del self.score_animations['home']

        self.canvas.draw_text(score_x, 24, home_score, *home_color)

        # MIDDLE SECTION: Pitcher info and bases
        # Pitcher label
        if game.current_pitcher:
            self.canvas.draw_text(2, 38, "Pitcher:", *Colors.WHITE)

            # Triangle indicator (batting team indicator)
            if game.inning.half == "top":
                # Draw triangle pointing at away team
                for i in range(3):
                    self.canvas.draw_line(50 + i, 32 - i, 50 + i, 32 + i, *Colors.WHITE)
            else:
                # Draw triangle pointing at home team
                for i in range(3):
                    self.canvas.draw_line(50 + i, 35 - i, 50 + i, 35 + i, *Colors.WHITE)

        # Baseball diamond - individual base indicators (right side)
        if self.config.modes.live_game.show_runners:
            base_x = 90
            base_y = 30

            # Draw diamond outlines and fill if runner present
            # First base (bottom right)
            color = Colors.WHITE if game.runners.first else Colors.FINAL_GRAY
            self.canvas.draw_rect(base_x + 8, base_y + 8, 6, 6, *color, filled=game.runners.first is not None)

            # Second base (top center)
            color = Colors.WHITE if game.runners.second else Colors.FINAL_GRAY
            self.canvas.draw_rect(base_x + 4, base_y, 6, 6, *color, filled=game.runners.second is not None)

            # Third base (bottom left)
            color = Colors.WHITE if game.runners.third else Colors.FINAL_GRAY
            self.canvas.draw_rect(base_x, base_y + 8, 6, 6, *color, filled=game.runners.third is not None)

        # BOTTOM SECTION: At bat info and count
        # AB: [name] [count]
        if game.current_batter:
            batter_name = game.current_batter.name.split()[-1][:2]  # First 2 letters like "Ca"
            self.canvas.draw_text(2, 50, "AB:", *Colors.WHITE)
            self.canvas.draw_text(25, 50, batter_name, *Colors.WHITE)

            # Count as "B-S" format
            count_text = f"{game.count.balls}-{game.count.strikes}"
            self.canvas.draw_text(60, 50, count_text, *Colors.WHITE)

            # Outs as squares (right side)
            if self.config.modes.live_game.show_outs:
                out_x = 95
                for i in range(3):
                    if i < game.count.outs:
                        self.canvas.draw_rect(out_x + (i * 10), 44, 6, 6, *Colors.WHITE, filled=True)
                    else:
                        self.canvas.draw_rect(out_x + (i * 10), 44, 6, 6, *Colors.WHITE, filled=False)

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
