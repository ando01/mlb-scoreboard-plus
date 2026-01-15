"""Detailed stats renderer."""
from .base_renderer import BaseRenderer
from .graphics import Colors
from ..models.game import LiveGameData


class StatsRenderer(BaseRenderer):
    """Renders detailed player statistics."""

    def render(self, game: LiveGameData):
        """Render detailed stats for current game."""
        self.clear()

        # Title
        self.canvas.draw_text(5, 8, "STATS", *Colors.CYAN)

        # Current matchup
        if game.current_batter and game.current_pitcher:
            # Batter section
            self.canvas.draw_text(5, 20, "BATTER", *Colors.YELLOW)
            batter_name = game.current_batter.name.split()[-1][:12]
            self.canvas.draw_text(5, 30, batter_name, *Colors.WHITE)

            y = 40
            if game.current_batter.avg:
                self.canvas.draw_text(5, y, f"AVG: {game.current_batter.avg}", *Colors.WHITE)
                y += 10
            if game.current_batter.hr is not None:
                self.canvas.draw_text(5, y, f"HR: {game.current_batter.hr}", *Colors.WHITE)
                y += 10
            if game.current_batter.rbi is not None:
                self.canvas.draw_text(5, y, f"RBI: {game.current_batter.rbi}", *Colors.WHITE)

            # Pitcher section
            self.canvas.draw_text(70, 20, "PITCHER", *Colors.ORANGE)
            pitcher_name = game.current_pitcher.name.split()[-1][:12]
            self.canvas.draw_text(70, 30, pitcher_name, *Colors.WHITE)

            y = 40
            if game.current_pitcher.era:
                self.canvas.draw_text(70, y, f"ERA: {game.current_pitcher.era}", *Colors.WHITE)
                y += 10
            if game.current_pitcher.so is not None:
                self.canvas.draw_text(70, y, f"SO: {game.current_pitcher.so}", *Colors.WHITE)

        else:
            # No active matchup
            self.canvas.draw_text(10, 30, "No active at-bat", *Colors.FINAL_GRAY)

        self.canvas.swap()
