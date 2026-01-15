"""Canvas abstraction for LED matrix."""
import os
from typing import Optional, Tuple


class Canvas:
    """Abstraction layer for LED matrix canvas."""

    def __init__(self, width: int = 128, height: int = 64):
        self.width = width
        self.height = height
        self._matrix = None
        self._canvas = None
        self._dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'

        if not self._dev_mode:
            try:
                from rgbmatrix import RGBMatrix, RGBMatrixOptions
                options = RGBMatrixOptions()
                options.rows = int(os.getenv('LED_ROWS', 64))
                options.cols = int(os.getenv('LED_COLS', 128))
                options.chain_length = int(os.getenv('LED_CHAIN', 1))
                options.parallel = int(os.getenv('LED_PARALLEL', 1))
                options.brightness = int(os.getenv('LED_BRIGHTNESS', 60))
                options.hardware_mapping = os.getenv('LED_GPIO_MAPPING', 'adafruit-hat')
                options.gpio_slowdown = int(os.getenv('LED_GPIO_SLOWDOWN', 4))
                options.drop_privileges = False
                options.disable_hardware_pulsing = True

                self._matrix = RGBMatrix(options=options)
                self._canvas = self._matrix.CreateFrameCanvas()
            except ImportError:
                print("Warning: rgbmatrix not available, using emulator mode")
                self._dev_mode = True

        if self._dev_mode:
            # Development mode - use emulator or mock
            try:
                from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
                options = RGBMatrixOptions()
                options.rows = height
                options.cols = width
                self._matrix = RGBMatrix(options=options)
                self._canvas = self._matrix.CreateFrameCanvas()
            except ImportError:
                # Mock canvas for testing without emulator
                self._canvas = MockCanvas(width, height)

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int):
        """Set a single pixel."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._canvas.SetPixel(x, y, r, g, b)

    def clear(self):
        """Clear the canvas."""
        self._canvas.Clear()

    def draw_text(self, x: int, y: int, text: str, r: int, g: int, b: int, font=None):
        """Draw text on canvas."""
        if hasattr(self._canvas, 'DrawText'):
            from rgbmatrix import graphics
            if font is None:
                font = graphics.Font()
                font.LoadFont("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
            color = graphics.Color(r, g, b)
            return graphics.DrawText(self._canvas, font, x, y, color, text)
        else:
            # Mock implementation
            return len(text) * 6

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, r: int, g: int, b: int):
        """Draw a line."""
        # Bresenham's line algorithm
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        x, y = x1, y1
        while True:
            self.set_pixel(x, y, r, g, b)
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def draw_rect(self, x: int, y: int, w: int, h: int, r: int, g: int, b: int, filled: bool = False):
        """Draw a rectangle."""
        if filled:
            for py in range(y, y + h):
                for px in range(x, x + w):
                    self.set_pixel(px, py, r, g, b)
        else:
            self.draw_line(x, y, x + w - 1, y, r, g, b)
            self.draw_line(x + w - 1, y, x + w - 1, y + h - 1, r, g, b)
            self.draw_line(x + w - 1, y + h - 1, x, y + h - 1, r, g, b)
            self.draw_line(x, y + h - 1, x, y, r, g, b)

    def draw_circle(self, cx: int, cy: int, radius: int, r: int, g: int, b: int, filled: bool = False):
        """Draw a circle."""
        x = radius
        y = 0
        err = 0

        while x >= y:
            if filled:
                self.draw_line(cx - x, cy + y, cx + x, cy + y, r, g, b)
                self.draw_line(cx - x, cy - y, cx + x, cy - y, r, g, b)
                self.draw_line(cx - y, cy + x, cx + y, cy + x, r, g, b)
                self.draw_line(cx - y, cy - x, cx + y, cy - x, r, g, b)
            else:
                self.set_pixel(cx + x, cy + y, r, g, b)
                self.set_pixel(cx + y, cy + x, r, g, b)
                self.set_pixel(cx - y, cy + x, r, g, b)
                self.set_pixel(cx - x, cy + y, r, g, b)
                self.set_pixel(cx - x, cy - y, r, g, b)
                self.set_pixel(cx - y, cy - x, r, g, b)
                self.set_pixel(cx + y, cy - x, r, g, b)
                self.set_pixel(cx + x, cy - y, r, g, b)

            if err <= 0:
                y += 1
                err += 2 * y + 1
            if err > 0:
                x -= 1
                err -= 2 * x + 1

    def swap(self):
        """Swap buffers and display."""
        if self._matrix and hasattr(self._matrix, 'SwapOnVSync'):
            self._canvas = self._matrix.SwapOnVSync(self._canvas)
        elif hasattr(self._canvas, 'display'):
            self._canvas.display()


class MockCanvas:
    """Mock canvas for testing."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.buffer = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]

    def SetPixel(self, x: int, y: int, r: int, g: int, b: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.buffer[y][x] = (r, g, b)

    def Clear(self):
        self.buffer = [[(0, 0, 0) for _ in range(self.width)] for _ in range(self.height)]
