"""Live game renderer with animations."""
from typing import Optional
from .base_renderer import BaseRenderer
from .graphics import Colors, draw_baseball_diamond, draw_outs, draw_count
from .animations import (
    AnimationManager, ScoreChangeAnimation, RunnerAnimation,
    PulseAnimation, SlideAnimation
)
from ..models.game import LiveGameData, GameState, parse_game_state


class LiveGameRenderer(BaseRenderer):
    """Renders live game with animated play-by-play."""

    def __init__(self, canvas, config):
        super().__init__(canvas, config)
        self.animation_manager = AnimationManager()
        self.last_game_state: Optional[LiveGameData] = None
        self.score_animations = {}
        self.live_pulse = PulseAnimation(duration=2.0)
        self.live_pulse.start()

        # Load smaller font for pitcher/batter info
        self.small_font = canvas.load_font("5x7.bdf")

    def render(self, game: LiveGameData):
        """Render live game display."""
        self.clear()

        # Check for score changes and trigger animations
        if self.last_game_state:
            self._check_for_animations(game)

        # Update animations
        self.animation_manager.update()

        # Render based on game state
        _pregame_states = (GameState.PREVIEW, GameState.PREGAME, GameState.SCHEDULED)
        _live_states = (GameState.LIVE, GameState.IN_PROGRESS, GameState.WARMUP)
        _final_states = (GameState.FINAL, GameState.GAME_OVER)

        if game.state in _pregame_states:
            self._render_pregame(game)
        elif game.state in _live_states:
            self._render_live_game(game)
        elif game.state in _final_states:
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

        self.canvas.draw_text(5, 11, game.away_team.abbreviation, *away_color)
        self.canvas.draw_text(5, 23, game.home_team.abbreviation, *home_color)

        # "vs" separator
        self.canvas.draw_text(35, 17, "vs", *Colors.FINAL_GRAY)

        # Game time — convert UTC to local wall-clock time
        local_start = game.start_time.astimezone()
        time_str = local_start.strftime("%I:%M %p").lstrip("0")
        self.canvas.draw_text(5, 38, time_str, *Colors.CYAN)

        # Probable pitchers if available
        if game.probable_pitcher_away:
            pitcher_text = game.probable_pitcher_away.split()[-1][:8]  # Last name
            self.canvas.draw_text(55, 11, f"P: {pitcher_text}", *Colors.YELLOW)

        if game.probable_pitcher_home:
            pitcher_text = game.probable_pitcher_home.split()[-1][:8]
            self.canvas.draw_text(55, 23, f"P: {pitcher_text}", *Colors.YELLOW)

    @staticmethod
    def _format_name(name: str) -> str:
        """Return a name in 'J.Duran' format (first initial + last name).

        Handles multiple source formats:
          'Jhoan Duran'  → 'J.Duran'
          'J. Duran'     → 'J.Duran'
          'Duran, J.'    → 'J.Duran'   (boxscoreName style)
          'Duran'        → 'Duran'      (no initial available)
        """
        if not name:
            return name
        # "Last, F." style (common MLB boxscoreName)
        if ',' in name:
            parts = name.split(',', 1)
            last = parts[0].strip()
            first_part = parts[1].strip()
            initial = first_part[0] if first_part else ''
            return f"{initial}.{last}" if initial else last
        # "First Last" or "F. Last" style
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}.{parts[-1]}"
        return name

    def _render_end_of_inning(self, game: LiveGameData):
        """Render end-of-inning screen: score + next 3 batters."""
        away_color = Colors.get_team_color(game.away_team.abbreviation)
        home_color = Colors.get_team_color(game.home_team.abbreviation)

        # Keep the same team-color bars so the display feels continuous
        self.canvas.draw_rect(0, 0, 128, 12, *away_color, filled=True)
        self.canvas.draw_text(2, 10, game.away_team.abbreviation, *Colors.WHITE)
        self.canvas.draw_text(30, 10, str(game.away_team.score).rjust(2), *Colors.WHITE)

        self.canvas.draw_rect(0, 13, 128, 12, *home_color, filled=True)
        self.canvas.draw_text(2, 23, game.home_team.abbreviation, *Colors.WHITE)
        self.canvas.draw_text(30, 23, str(game.home_team.score).rjust(2), *Colors.WHITE)

        # "END TOP 3RD" / "END BOT 5TH" header
        half_str = "TOP" if game.inning.half == "top" else "BOT"
        header = f"END {half_str} {game.inning.ordinal.upper()}"
        self.canvas.draw_text(2, 35, header, *Colors.ORANGE, font=self.small_font)

        # "NEXT UP" label right-side
        self.canvas.draw_text(75, 35, "NEXT UP", *Colors.CYAN, font=self.small_font)

        # Next three batters, one per row
        for i, name in enumerate(game.next_batters[:3]):
            batter_text = f"{i + 1}. {self._format_name(name)}"
            self.canvas.draw_text(2, 44 + i * 9, batter_text, *Colors.WHITE, font=self.small_font)

    def _render_live_game(self, game: LiveGameData):
        """Render live game - exact match to original mlb-led-scoreboard."""
        # Show end-of-inning screen when 3 outs and next batters are known
        if game.count.outs >= 3 and game.next_batters:
            self._render_end_of_inning(game)
            return


        # Get team colors
        away_team_color = Colors.get_team_color(game.away_team.abbreviation)
        home_team_color = Colors.get_team_color(game.home_team.abbreviation)

        # TOP BAR: Away team (0-12 pixels high)
        self.canvas.draw_rect(0, 0, 128, 12, *away_team_color, filled=True)
        self.canvas.draw_text(2, 10, game.away_team.abbreviation, *Colors.WHITE)

        # R-H-E display: three right-justified columns (Runs Hits Errors)
        # Right-justify each number to prevent crowding with double digits
        away_r = str(game.away_team.score).rjust(2)
        away_h = str(game.away_team.hits).rjust(2)
        away_e = str(game.away_team.errors).rjust(1)
        self.canvas.draw_text(80, 10, away_r, *Colors.WHITE)
        self.canvas.draw_text(96, 10, away_h, *Colors.WHITE)
        self.canvas.draw_text(114, 10, away_e, *Colors.WHITE)

        # SECOND BAR: Home team (13-25 pixels high)
        self.canvas.draw_rect(0, 13, 128, 12, *home_team_color, filled=True)
        self.canvas.draw_text(2, 23, game.home_team.abbreviation, *Colors.WHITE)

        # R-H-E display: three right-justified columns (Runs Hits Errors)
        # Right-justify each number to prevent crowding with double digits
        home_r = str(game.home_team.score).rjust(2)
        home_h = str(game.home_team.hits).rjust(2)
        home_e = str(game.home_team.errors).rjust(1)
        self.canvas.draw_text(80, 23, home_r, *Colors.WHITE)
        self.canvas.draw_text(96, 23, home_h, *Colors.WHITE)
        self.canvas.draw_text(114, 23, home_e, *Colors.WHITE)

        # MIDDLE SECTION: P: [pitcher name] with ERA and pitch info below
        if game.current_pitcher:
            pitcher_name = self._format_name(game.current_pitcher.name)
            pitcher_text = f"P:{pitcher_name}"
            self.canvas.draw_text(2, 34, pitcher_text, *Colors.WHITE, font=self.small_font)

            # Show either pitch count (before pitch) or pitch result (after pitch)
            if game.show_pitch_result:
                # Show pitch type and velocity after pitch is thrown
                if game.last_pitch_type or game.last_pitch_speed:
                    pitch_info = ""
                    if game.last_pitch_type:
                        pitch_info = game.last_pitch_type[:2].upper()  # Abbreviate pitch type (e.g., FF, SL)
                    if game.last_pitch_speed:
                        speed = f"{int(game.last_pitch_speed)}mph"
                        pitch_info = f"{pitch_info} {speed}" if pitch_info else speed
                    if pitch_info:
                        self.canvas.draw_text(45, 43, pitch_info, *Colors.CYAN, font=self.small_font)
            else:
                # Show pitch count before pitch is thrown
                if game.pitch_count is not None:
                    pitch_count_text = f"P{game.pitch_count}"
                    self.canvas.draw_text(45, 43, pitch_count_text, *Colors.WHITE, font=self.small_font)

        # Baseball diamond - rotated squares (diamonds) on right
        if self.config.modes.live_game.show_runners:
            base_x = 108
            base_y = 32
            diamond_size = 6  # Half-width of diamond (increased from 4)

            # Draw diamonds (rotated 45 degrees) for each base
            # Second base (top center)
            if game.runners.second:
                # Filled yellow diamond
                for dy in range(-diamond_size, diamond_size + 1):
                    width = diamond_size - abs(dy)
                    for dx in range(-width, width + 1):
                        self.canvas.set_pixel(base_x + dx, base_y + dy, *Colors.YELLOW)
            else:
                # Empty white diamond outline
                self.canvas.draw_line(base_x, base_y - diamond_size, base_x + diamond_size, base_y, *Colors.WHITE)
                self.canvas.draw_line(base_x + diamond_size, base_y, base_x, base_y + diamond_size, *Colors.WHITE)
                self.canvas.draw_line(base_x, base_y + diamond_size, base_x - diamond_size, base_y, *Colors.WHITE)
                self.canvas.draw_line(base_x - diamond_size, base_y, base_x, base_y - diamond_size, *Colors.WHITE)

            # Third base (left)
            third_x = base_x - 11
            third_y = base_y + 8
            if game.runners.third:
                for dy in range(-diamond_size, diamond_size + 1):
                    width = diamond_size - abs(dy)
                    for dx in range(-width, width + 1):
                        self.canvas.set_pixel(third_x + dx, third_y + dy, *Colors.YELLOW)
            else:
                self.canvas.draw_line(third_x, third_y - diamond_size, third_x + diamond_size, third_y, *Colors.WHITE)
                self.canvas.draw_line(third_x + diamond_size, third_y, third_x, third_y + diamond_size, *Colors.WHITE)
                self.canvas.draw_line(third_x, third_y + diamond_size, third_x - diamond_size, third_y, *Colors.WHITE)
                self.canvas.draw_line(third_x - diamond_size, third_y, third_x, third_y - diamond_size, *Colors.WHITE)

            # First base (right)
            first_x = base_x + 11
            first_y = base_y + 8
            if game.runners.first:
                for dy in range(-diamond_size, diamond_size + 1):
                    width = diamond_size - abs(dy)
                    for dx in range(-width, width + 1):
                        self.canvas.set_pixel(first_x + dx, first_y + dy, *Colors.YELLOW)
            else:
                self.canvas.draw_line(first_x, first_y - diamond_size, first_x + diamond_size, first_y, *Colors.WHITE)
                self.canvas.draw_line(first_x + diamond_size, first_y, first_x, first_y + diamond_size, *Colors.WHITE)
                self.canvas.draw_line(first_x, first_y + diamond_size, first_x - diamond_size, first_y, *Colors.WHITE)
                self.canvas.draw_line(first_x - diamond_size, first_y, first_x, first_y - diamond_size, *Colors.WHITE)

        # BOTTOM SECTION: B: [batter] [count] with BA below and out squares
        if game.current_batter:
            batter_name = self._format_name(game.current_batter.name)
            count_text = f"{game.count.balls}-{game.count.strikes}"

            # Batter name and count on same line
            ab_text = f"B:{batter_name} {count_text}"
            self.canvas.draw_text(2, 54, ab_text, *Colors.WHITE, font=self.small_font)

            # INNING DISPLAY: Show inning number with arrow near outs
            if game.inning:
                inning_num = str(game.inning.num)
                # Arrow color: green for top, red for bottom
                arrow = "▲" if game.inning.half == "top" else "▼"
                arrow_color = Colors.LIVE_GREEN if game.inning.half == "top" else Colors.RED

                # Draw arrow and number together (smaller font), positioned near outs
                inning_text = f"{arrow}{inning_num}"
                self.canvas.draw_text(68, 54, inning_text, *arrow_color, font=self.small_font)

            # Outs as smaller squares on right
            if self.config.modes.live_game.show_outs:
                out_x = 100
                for i in range(3):
                    if i < game.count.outs:
                        self.canvas.draw_rect(out_x + (i * 7), 52, 4, 4, *Colors.WHITE, filled=True)
                    else:
                        self.canvas.draw_rect(out_x + (i * 7), 52, 4, 4, *Colors.WHITE, filled=False)

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
