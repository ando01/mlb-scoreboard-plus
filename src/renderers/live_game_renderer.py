"""Live game renderer with animations."""
import time
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

        # Broadcast networks (TV/streaming) below the game time row
        if game.broadcasts:
            self._render_pregame_broadcasts(game.broadcasts)

    def _render_pregame_broadcasts(self, broadcasts):
        """Render broadcast network names at y=50, scrolling if needed."""
        _MLBTV = {"mlb.tv", "mlbtv"}

        def sort_key(b):
            nm = b.name.lower()
            if nm in _MLBTV:
                return 3          # MLB.TV last — always available for subscribers
            if b.is_national:
                return 0          # National TV (ESPN, TBS, FOX…) first
            if b.free_game:
                return 1          # Free streaming (Peacock, Apple TV+…) second
            return 2              # Local/RSN third

        ordered = sorted(broadcasts, key=sort_key)
        text = " / ".join(b.name for b in ordered)

        LABEL_X = 2
        TEXT_X = 20   # x position after the "TV:" label
        ROW_Y = 50

        self.canvas.draw_text(LABEL_X, ROW_Y, "TV:", *Colors.FINAL_GRAY, font=self.small_font)

        # 5x7 BDF font: each character is ~6px wide including spacing
        CHAR_W = 6
        avail_px = 128 - TEXT_X   # 108 px available for the network text
        text_px = len(text) * CHAR_W

        if text_px <= avail_px:
            self.canvas.draw_text(TEXT_X, ROW_Y, text, *Colors.CYAN, font=self.small_font)
        else:
            # Scroll right-to-left at 25 px/second, looping seamlessly
            total = avail_px + text_px
            offset = int((time.time() * 25) % total)
            actual_x = (TEXT_X + avail_px) - offset
            self.canvas.draw_text(actual_x, ROW_Y, text, *Colors.CYAN, font=self.small_font)

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

        # Next three batters, one per row — show actual lineup position (1–9)
        for i, name in enumerate(game.next_batters[:3]):
            pos = game.next_batter_positions[i] if i < len(game.next_batter_positions) else (i + 1)
            batter_text = f"{pos}. {self._format_name(name)}"
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

        # ── LEFT COLUMN ────────────────────────────────────────────────────
        # Row y=34 — Pitcher name
        if game.current_pitcher:
            pitcher_name = self._format_name(game.current_pitcher.name)
            self.canvas.draw_text(2, 34, f"P:{pitcher_name}", *Colors.WHITE, font=self.small_font)

        # Row y=43 — Pitch count or last pitch type/speed
        if game.current_pitcher:
            if game.show_pitch_result and (game.last_pitch_type or game.last_pitch_speed):
                pitch_info = ""
                if game.last_pitch_type:
                    pitch_info = game.last_pitch_type[:2].upper()
                if game.last_pitch_speed:
                    speed = f"{int(game.last_pitch_speed)}mph"
                    pitch_info = f"{pitch_info} {speed}" if pitch_info else speed
                if pitch_info:
                    self.canvas.draw_text(2, 43, pitch_info, *Colors.CYAN, font=self.small_font)
            elif game.pitch_count is not None:
                self.canvas.draw_text(2, 43, f"P:{game.pitch_count}", *Colors.WHITE, font=self.small_font)

        # Row y=52 — At-bat result (shows briefly after play, then clears)
        if game.last_at_bat_result:
            _hits_walks = {"1B", "2B", "3B", "HR", "BB", "IBB", "HBP"}
            _errors_special = {"E", "FC", "SF", "SH", "GDP", "DP", "TP"}
            result = game.last_at_bat_result
            if result in _hits_walks:
                result_color = Colors.LIVE_GREEN
            elif result in _errors_special:
                result_color = Colors.YELLOW
            else:
                result_color = Colors.WHITE
            self.canvas.draw_text(2, 52, result, *result_color, font=self.small_font)

        # Row y=62 — Batter name + game hits-AB in parens
        if game.current_batter:
            batter_name = self._format_name(game.current_batter.name)
            batter_text = f"B:{batter_name}"
            if game.current_batter.hits is not None and game.current_batter.at_bats is not None:
                batter_text += f" ({game.current_batter.hits}-{game.current_batter.at_bats})"
            self.canvas.draw_text(2, 62, batter_text, *Colors.WHITE, font=self.small_font)

        # ── BALL / STRIKE / OUT CIRCLES ────────────────────────────────────
        # Labels at x=53, circles at x=65/71/77[/83], radius=2
        # Filled = active count; FINAL_GRAY outline = not yet reached

        # Balls — 4 green circles
        self.canvas.draw_text(53, 34, "B:", *Colors.WHITE, font=self.small_font)
        for i in range(4):
            cx = 65 + i * 6
            if i < game.count.balls:
                self.canvas.draw_circle(cx, 31, 2, *Colors.LIVE_GREEN, filled=True)
            else:
                self.canvas.draw_circle(cx, 31, 2, *Colors.FINAL_GRAY, filled=False)

        # Strikes — 3 red circles
        self.canvas.draw_text(53, 43, "S:", *Colors.WHITE, font=self.small_font)
        for i in range(3):
            cx = 65 + i * 6
            if i < game.count.strikes:
                self.canvas.draw_circle(cx, 40, 2, *Colors.RED, filled=True)
            else:
                self.canvas.draw_circle(cx, 40, 2, *Colors.FINAL_GRAY, filled=False)

        # Outs — 3 red circles
        self.canvas.draw_text(53, 52, "O:", *Colors.WHITE, font=self.small_font)
        for i in range(3):
            cx = 65 + i * 6
            if i < game.count.outs:
                self.canvas.draw_circle(cx, 49, 2, *Colors.RED, filled=True)
            else:
                self.canvas.draw_circle(cx, 49, 2, *Colors.FINAL_GRAY, filled=False)

        # ── INNING MARKER ─────────────────────────────────────────────────
        # Centered under the base diamonds (diamond cluster center x≈108)
        if game.inning:
            arrow = "▲" if game.inning.half == "top" else "▼"
            arrow_color = Colors.LIVE_GREEN if game.inning.half == "top" else Colors.RED
            self.canvas.draw_text(104, 57, f"{arrow}{game.inning.num}", *arrow_color, font=self.small_font)

        # ── BASE DIAMONDS ──────────────────────────────────────────────────
        if self.config.modes.live_game.show_runners:
            base_x = 108
            base_y = 32
            diamond_size = 6

            # Second base (top center)
            if game.runners.second:
                for dy in range(-diamond_size, diamond_size + 1):
                    width = diamond_size - abs(dy)
                    for dx in range(-width, width + 1):
                        self.canvas.set_pixel(base_x + dx, base_y + dy, *Colors.YELLOW)
            else:
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
