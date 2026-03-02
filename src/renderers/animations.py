"""Animation system for smooth transitions and effects."""
import time
from typing import Callable, Optional, Tuple
from enum import Enum
import math


class EasingFunction(Enum):
    """Easing functions for animations."""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BOUNCE = "bounce"


class Animation:
    """Base animation class."""

    def __init__(self, duration: float, easing: EasingFunction = EasingFunction.LINEAR):
        self.duration = duration
        self.easing = easing
        self.start_time: Optional[float] = None
        self.complete = False

    def start(self):
        """Start the animation."""
        self.start_time = time.time()
        self.complete = False

    def get_progress(self) -> float:
        """Get animation progress (0.0 to 1.0)."""
        if self.start_time is None:
            return 0.0

        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            self.complete = True
            return 1.0

        progress = elapsed / self.duration
        return self._apply_easing(progress)

    def _apply_easing(self, t: float) -> float:
        """Apply easing function."""
        if self.easing == EasingFunction.LINEAR:
            return t
        elif self.easing == EasingFunction.EASE_IN:
            return t * t
        elif self.easing == EasingFunction.EASE_OUT:
            return 1 - (1 - t) * (1 - t)
        elif self.easing == EasingFunction.EASE_IN_OUT:
            if t < 0.5:
                return 2 * t * t
            else:
                return 1 - 2 * (1 - t) * (1 - t)
        elif self.easing == EasingFunction.BOUNCE:
            if t < 0.5:
                return 8 * t * t * t * t
            else:
                f = (t - 1)
                return 1 + 8 * f * f * f * f
        return t

    def is_complete(self) -> bool:
        """Check if animation is complete."""
        return self.complete


class SlideAnimation(Animation):
    """Slide animation from start to end position."""

    def __init__(self, start: int, end: int, duration: float = 0.5,
                 easing: EasingFunction = EasingFunction.EASE_OUT):
        super().__init__(duration, easing)
        self.start = start
        self.end = end

    def get_position(self) -> int:
        """Get current position."""
        progress = self.get_progress()
        return int(self.start + (self.end - self.start) * progress)


class FadeAnimation(Animation):
    """Fade animation from start to end alpha."""

    def __init__(self, start: float = 0.0, end: float = 1.0, duration: float = 0.5):
        super().__init__(duration)
        self.start = start
        self.end = end

    def get_alpha(self) -> float:
        """Get current alpha value."""
        progress = self.get_progress()
        return self.start + (self.end - self.start) * progress


class PulseAnimation(Animation):
    """Pulsing animation (repeating)."""

    def __init__(self, duration: float = 1.0):
        super().__init__(duration)

    def get_scale(self) -> float:
        """Get current scale (0.8 to 1.2)."""
        progress = self.get_progress()
        # Use sine wave for smooth pulsing
        return 1.0 + 0.2 * math.sin(progress * 2 * math.pi)

    def is_complete(self) -> bool:
        """Pulse never completes (loops)."""
        if self.complete:
            self.start()  # Restart
        return False


class ScoreChangeAnimation(Animation):
    """Animation for score changes with celebration."""

    def __init__(self, old_score: int, new_score: int, duration: float = 2.0):
        super().__init__(duration)
        self.old_score = old_score
        self.new_score = new_score
        self.is_increase = new_score > old_score

    def get_display_score(self) -> int:
        """Get score to display."""
        return self.new_score

    def get_flash_state(self) -> bool:
        """Get whether to flash the score."""
        progress = self.get_progress()
        if progress < 0.5:
            # Flash 4 times in first half
            return int(progress * 16) % 2 == 0
        return True

    def get_color_intensity(self) -> float:
        """Get color intensity for celebration."""
        progress = self.get_progress()
        if progress < 0.5:
            return 1.0
        else:
            # Fade from bright to normal
            return 1.0 - (progress - 0.5) * 2 * 0.5


class RunnerAnimation(Animation):
    """Animation for runner advancing on bases."""

    def __init__(self, start_base: int, end_base: int, duration: float = 1.0):
        """
        Args:
            start_base: 0=home, 1=first, 2=second, 3=third, 4=home (score)
            end_base: Target base
        """
        super().__init__(duration, EasingFunction.EASE_IN_OUT)
        self.start_base = start_base
        self.end_base = end_base

    def get_position_on_diamond(self) -> Tuple[float, float]:
        """Get current position as fraction of diamond (0-1, 0-1)."""
        progress = self.get_progress()

        # Define base positions (normalized to 0-1)
        positions = {
            0: (0.5, 0.9),   # Home
            1: (0.9, 0.5),   # First
            2: (0.5, 0.1),   # Second
            3: (0.1, 0.5),   # Third
            4: (0.5, 0.9),   # Home (scoring)
        }

        start_pos = positions[self.start_base]
        end_pos = positions[self.end_base]

        x = start_pos[0] + (end_pos[0] - start_pos[0]) * progress
        y = start_pos[1] + (end_pos[1] - start_pos[1]) * progress

        return (x, y)


class HomeRunAnimation(Animation):
    """Full-screen celebration for home runs and grand slams."""

    def __init__(self, team_color: Tuple[int, int, int], batter_name: str = "",
                 is_grand_slam: bool = False, hr_count: Optional[int] = None):
        duration = 4.0 if is_grand_slam else 3.0
        super().__init__(duration)
        self.team_color = team_color
        self.batter_name = batter_name
        self.is_grand_slam = is_grand_slam
        self.hr_count = hr_count

    def get_flash_state(self) -> bool:
        """Alternating flash during opening phase."""
        progress = self.get_progress()
        if progress < 0.3:
            return int(progress * 20) % 2 == 0
        return True

    def get_intensity(self) -> float:
        """Brightness multiplier — fades to black at end."""
        progress = self.get_progress()
        if progress < 0.8:
            return 1.0
        return 1.0 - (progress - 0.8) / 0.2


class StrikeoutAnimation(Animation):
    """Full-screen animation for strikeouts."""

    def __init__(self, pitcher_name: str = "",
                 pitching_team_color: Tuple[int, int, int] = (255, 255, 255)):
        super().__init__(2.0)
        self.pitcher_name = pitcher_name
        self.pitching_team_color = pitching_team_color

    def get_flash_state(self) -> bool:
        """Alternating flash during opening phase."""
        progress = self.get_progress()
        if progress < 0.4:
            return int(progress * 16) % 2 == 0
        return True

    def get_intensity(self) -> float:
        """Brightness multiplier — fades to black at end."""
        progress = self.get_progress()
        if progress < 0.8:
            return 1.0
        return 1.0 - (progress - 0.8) / 0.2


class AnimationManager:
    """Manages multiple animations."""

    def __init__(self):
        self.animations: list[Animation] = []

    def add(self, animation: Animation):
        """Add an animation."""
        animation.start()
        self.animations.append(animation)

    def update(self):
        """Update all animations and remove completed ones."""
        self.animations = [
            anim for anim in self.animations
            if not anim.is_complete()
        ]

    def clear(self):
        """Clear all animations."""
        self.animations.clear()

    def has_active_animations(self) -> bool:
        """Check if any animations are active."""
        return len(self.animations) > 0
