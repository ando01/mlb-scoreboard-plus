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
        # Load smaller font for better column spacing
        self.small_font = canvas.load_font("5x7.bdf")

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
        self.canvas.draw_text(2, 8, div_name, *Colors.CYAN)

        # Column headers - using smaller font with better spacing
        self.canvas.draw_text(2, 18, "TEAM", *Colors.YELLOW, font=self.small_font)
        self.canvas.draw_text(40, 18, "W", *Colors.YELLOW, font=self.small_font)
        self.canvas.draw_text(58, 18, "L", *Colors.YELLOW, font=self.small_font)
        self.canvas.draw_text(76, 18, "PCT", *Colors.YELLOW, font=self.small_font)
        self.canvas.draw_text(104, 18, "GB", *Colors.YELLOW, font=self.small_font)

        # Teams (show up to 5)
        y = 27
        for i, team in enumerate(teams[:5]):
            if y > 60:
                break

            # Highlight favorite team
            color = Colors.GREEN if team.team_abbr == self.config.teams.favorite else Colors.WHITE

            # Right-justify numbers for clean columns
            wins_str = str(team.wins).rjust(2)
            losses_str = str(team.losses).rjust(2)
            pct_str = team.pct.rjust(4)
            gb_str = team.gb.rjust(4)

            self.canvas.draw_text(2, y, team.team_abbr, *color, font=self.small_font)
            self.canvas.draw_text(40, y, wins_str, *color, font=self.small_font)
            self.canvas.draw_text(58, y, losses_str, *color, font=self.small_font)
            self.canvas.draw_text(76, y, pct_str, *color, font=self.small_font)
            self.canvas.draw_text(104, y, gb_str, *color, font=self.small_font)

            y += 9

        self.canvas.swap()

    def next_division(self):
        """Move to next division."""
        self.current_division_index += 1
