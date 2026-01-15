"""Graphics utilities and color definitions."""
from typing import Tuple

# Color definitions (R, G, B)
class Colors:
    """Standard colors for scoreboard."""
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    ORANGE = (255, 165, 0)
    CYAN = (0, 255, 255)
    MAGENTA = (255, 0, 255)

    # Team colors dictionary - actual MLB team colors
    TEAM_COLORS = {
        'NYY': (12, 35, 64),      # Yankees - Navy
        'BOS': (189, 48, 57),     # Red Sox - Red
        'LAD': (0, 90, 156),      # Dodgers - Blue
        'SFG': (253, 90, 30),     # Giants - Orange
        'HOU': (235, 110, 31),    # Astros - Orange
        'ATL': (206, 17, 65),     # Braves - Red
        'CHC': (14, 51, 134),     # Cubs - Blue
        'STL': (196, 30, 58),     # Cardinals - Red
        'TB': (9, 44, 92),        # Rays - Navy
        'TOR': (19, 74, 142),     # Blue Jays - Blue
        'BAL': (223, 70, 1),      # Orioles - Orange
        'SD': (47, 36, 29),       # Padres - Brown
        'ARI': (167, 25, 48),     # D-backs - Red
        'COL': (51, 0, 111),      # Rockies - Purple
    }

    @staticmethod
    def get_team_color(team_abbr: str):
        """Get team color, default to blue if not found."""
        return Colors.TEAM_COLORS.get(team_abbr, (0, 50, 150))

    # Status colors
    LIVE_GREEN = (0, 200, 0)
    FINAL_GRAY = (128, 128, 128)
    WARNING_AMBER = (255, 191, 0)


class Font:
    """Font loading and management."""

    _fonts = {}

    @classmethod
    def load(cls, name: str, size: int = 8):
        """Load a font (stub for now)."""
        key = f"{name}_{size}"
        if key not in cls._fonts:
            try:
                from rgbmatrix import graphics
                font = graphics.Font()
                # Try to load system fonts
                paths = [
                    f"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    f"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                ]
                for path in paths:
                    try:
                        font.LoadFont(path)
                        cls._fonts[key] = font
                        break
                    except:
                        continue
            except ImportError:
                cls._fonts[key] = None
        return cls._fonts.get(key)


def draw_baseball_diamond(canvas, x: int, y: int, size: int,
                         runners: Tuple[bool, bool, bool] = (False, False, False),
                         color: Tuple[int, int, int] = Colors.WHITE):
    """Draw a baseball diamond with runners."""
    # Draw diamond
    half = size // 2

    # Diamond outline
    canvas.draw_line(x, y + half, x + half, y, *color)  # Home to 1st
    canvas.draw_line(x + half, y, x + size, y + half, *color)  # 1st to 2nd
    canvas.draw_line(x + size, y + half, x + half, y + size, *color)  # 2nd to 3rd
    canvas.draw_line(x + half, y + size, x, y + half, *color)  # 3rd to home

    # Draw runners if present
    runner_color = Colors.YELLOW
    if runners[0]:  # First base
        canvas.draw_circle(x + half + 2, y + 2, 2, *runner_color, filled=True)
    if runners[1]:  # Second base
        canvas.draw_circle(x + size - 2, y + half, 2, *runner_color, filled=True)
    if runners[2]:  # Third base
        canvas.draw_circle(x + half + 2, y + size - 2, 2, *runner_color, filled=True)


def draw_outs(canvas, x: int, y: int, outs: int):
    """Draw out indicators."""
    for i in range(3):
        color = Colors.RED if i < outs else Colors.FINAL_GRAY
        canvas.draw_circle(x + i * 6, y, 2, *color, filled=True)


def draw_count(canvas, x: int, y: int, balls: int, strikes: int):
    """Draw ball-strike count."""
    # Balls
    for i in range(4):
        color = Colors.GREEN if i < balls else Colors.FINAL_GRAY
        canvas.draw_circle(x + i * 4, y, 1, *color, filled=True)

    # Strikes (below balls)
    for i in range(3):
        color = Colors.RED if i < strikes else Colors.FINAL_GRAY
        canvas.draw_circle(x + i * 4, y + 4, 1, *color, filled=True)


def scroll_text(canvas, text: str, x: int, y: int, offset: int,
                color: Tuple[int, int, int] = Colors.WHITE, font=None):
    """Draw scrolling text."""
    actual_x = x - offset
    return canvas.draw_text(actual_x, y, text, *color, font=font)
