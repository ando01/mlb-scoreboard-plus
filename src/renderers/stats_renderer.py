"""Detailed stats renderer."""
from .base_renderer import BaseRenderer
from .graphics import Colors
from ..models.game import LiveGameData


class StatsRenderer(BaseRenderer):
    """Renders detailed player statistics."""

    def __init__(self, canvas, config):
        super().__init__(canvas, config)
        # Load smaller font for better text spacing
        self.small_font = canvas.load_font("5x7.bdf")

    def render(self, game: LiveGameData):
        """Render detailed stats for current game."""
        self.clear()

        # Title
        self.canvas.draw_text(5, 8, "STATS", *Colors.CYAN)

        # Current matchup
        if game.current_batter and game.current_pitcher:
            # Batter section - using smaller font
            self.canvas.draw_text(3, 18, "BATTER", *Colors.YELLOW, font=self.small_font)
            batter_name = game.current_batter.name.split()[-1][:15]
            self.canvas.draw_text(3, 27, batter_name, *Colors.WHITE, font=self.small_font)

            y = 36
            if game.current_batter.avg:
                self.canvas.draw_text(3, y, f"AVG: {game.current_batter.avg}", *Colors.WHITE, font=self.small_font)
                y += 9
            if game.current_batter.hr is not None:
                self.canvas.draw_text(3, y, f"HR: {game.current_batter.hr}", *Colors.WHITE, font=self.small_font)
                y += 9
            if game.current_batter.rbi is not None:
                self.canvas.draw_text(3, y, f"RBI: {game.current_batter.rbi}", *Colors.WHITE, font=self.small_font)

            # Pitcher section - using smaller font
            self.canvas.draw_text(68, 18, "PITCHER", *Colors.ORANGE, font=self.small_font)
            pitcher_name = game.current_pitcher.name.split()[-1][:15]
            self.canvas.draw_text(68, 27, pitcher_name, *Colors.WHITE, font=self.small_font)

            y = 36
            if game.current_pitcher.era:
                self.canvas.draw_text(68, y, f"ERA: {game.current_pitcher.era}", *Colors.WHITE, font=self.small_font)
                y += 9
            if game.current_pitcher.so is not None:
                self.canvas.draw_text(68, y, f"SO: {game.current_pitcher.so}", *Colors.WHITE, font=self.small_font)

        else:
            # No active matchup
            self.canvas.draw_text(10, 30, "No active at-bat", *Colors.FINAL_GRAY, font=self.small_font)

        self.canvas.swap()
