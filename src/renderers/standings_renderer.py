"""Standings renderer."""
from typing import List
from .base_renderer import BaseRenderer
from .graphics import Colors, scroll_text
from ..models.game import StandingsEntry


class StandingsRenderer(BaseRenderer):
    """Renders division standings."""

    def __init__(self, canvas, config):
        super().__init__(canvas, config)
        self.scroll_offset = 0
        self.current_division_index = 0

    def render(self, standings: List[StandingsEntry]):
        """Render standings."""
        if not standings:
            self.clear()
            self.canvas.draw_text(10, 30, "No Standings", *Colors.WHITE)
            self.canvas.swap()
            return

        self.clear()

        # Group by division
        divisions = {}
        for entry in standings:
            if entry.division not in divisions:
                divisions[entry.division] = []
            divisions[entry.division].append(entry)

        # Get current division
        division_names = list(divisions.keys())
        if not division_names:
            return

        current_div = division_names[self.current_division_index % len(division_names)]
        teams = divisions[current_div]

        # Title
        div_name = current_div[:15]  # Truncate if too long
        self.canvas.draw_text(5, 8, div_name, *Colors.CYAN)

        # Column headers
        self.canvas.draw_text(5, 18, "TEAM", *Colors.YELLOW)
        self.canvas.draw_text(45, 18, "W", *Colors.YELLOW)
        self.canvas.draw_text(60, 18, "L", *Colors.YELLOW)
        self.canvas.draw_text(75, 18, "PCT", *Colors.YELLOW)
        self.canvas.draw_text(105, 18, "GB", *Colors.YELLOW)

        # Teams (show up to 5)
        y = 28
        for i, team in enumerate(teams[:5]):
            if y > 60:
                break

            # Highlight favorite team
            color = Colors.GREEN if team.team_abbr == self.config.teams.favorite else Colors.WHITE

            self.canvas.draw_text(5, y, team.team_abbr, *color)
            self.canvas.draw_text(45, y, str(team.wins), *color)
            self.canvas.draw_text(60, y, str(team.losses), *color)
            self.canvas.draw_text(75, y, team.pct, *color)
            self.canvas.draw_text(105, y, team.gb, *color)

            y += 10

        self.canvas.swap()

    def next_division(self):
        """Move to next division."""
        self.current_division_index += 1
