"""News renderer for off-season mode."""
from typing import List
from .base_renderer import BaseRenderer
from .graphics import Colors
import time


class NewsRenderer(BaseRenderer):
    """Renders MLB news headlines during off-season."""

    def __init__(self, canvas, config):
        super().__init__(canvas, config)
        # Load smaller font for news text
        self.small_font = canvas.load_font("5x7.bdf")
        self.scroll_offset = 0
        self.current_story_index = 0
        self.last_update = time.time()
        self.stories = []

    def set_stories(self, stories: List[dict]):
        """Set news stories to display."""
        self.stories = stories
        self.current_story_index = 0
        self.scroll_offset = 0

    def render(self):
        """Render news headlines with scrolling."""
        self.clear()

        if not self.stories:
            self.canvas.draw_text(10, 30, "Loading news...", *Colors.WHITE, font=self.small_font)
            self.canvas.swap()
            return

        # Get current story
        story = self.stories[self.current_story_index % len(self.stories)]

        # Title bar
        self.canvas.draw_text(2, 9, "MLB NEWS", *Colors.CYAN, font=self.small_font)

        # Story number (top right)
        story_num = f"{self.current_story_index + 1}/{len(self.stories)}"
        self.canvas.draw_text(108, 9, story_num, *Colors.FINAL_GRAY, font=self.small_font)

        # Source indicator (second line, left side under title)
        source = story.get('source', 'MLB')
        source_color = Colors.ORANGE if 'Trade Rumors' in source else Colors.LIVE_GREEN
        source_text = "MLBTR" if 'Trade Rumors' in source else "MLB"
        self.canvas.draw_text(2, 18, source_text, *source_color, font=self.small_font)

        # Headline (word-wrapped) - using small font (5x7)
        headline = story.get('title', 'No headline')

        # Word wrap headline to multiple lines
        words = headline.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if len(test_line) * 5 < 128:  # Rough estimate for 5x7 font width
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # Display up to 5 lines of headline
        y = 27
        for i, line in enumerate(lines[:5]):
            self.canvas.draw_text(2, y, line[:25], *Colors.WHITE, font=self.small_font)
            y += 9

        self.canvas.swap()

        # Auto-advance to next story every 13 seconds
        if time.time() - self.last_update > 13:
            self.current_story_index += 1
            self.last_update = time.time()

    def next_story(self):
        """Move to next story."""
        self.current_story_index += 1
        self.scroll_offset = 0
