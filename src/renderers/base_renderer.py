"""Base renderer class."""
from abc import ABC, abstractmethod
from .canvas import Canvas
from ..models.config import AppConfig


class BaseRenderer(ABC):
    """Base class for all renderers."""

    def __init__(self, canvas: Canvas, config: AppConfig):
        self.canvas = canvas
        self.config = config

    @abstractmethod
    def render(self, **kwargs):
        """Render content to canvas. Must be implemented by subclasses."""
        pass

    def clear(self):
        """Clear the canvas."""
        self.canvas.clear()
