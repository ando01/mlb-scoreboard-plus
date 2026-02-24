"""Canvas abstraction for LED matrix."""
import os
from pathlib import Path
from typing import Optional, Tuple

# Project root is three levels up from this file (src/renderers/canvas.py)
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _font_paths(font_name: str) -> list:
    """Return candidate BDF font paths in priority order.

    Checks the project-bundled copy first so the process works correctly
    whether run as root via systemd or interactively via sudo.
    """
    username = os.environ.get('SUDO_USER', os.environ.get('USER', 'pi'))
    return [
        # Project-local copy (works regardless of run-as user)
        str(_PROJECT_ROOT / "rpi-rgb-led-matrix" / "fonts" / font_name),
        # Custom override via env var
        os.path.join(os.environ.get('LED_FONT_PATH', ''), font_name) if os.environ.get('LED_FONT_PATH') else None,
        # User home fallbacks
        f"/home/{username}/rpi-rgb-led-matrix/fonts/{font_name}",
        f"/home/{username}/mlb-scoreboard-plus/rpi-rgb-led-matrix/fonts/{font_name}",
        f"/usr/local/share/fonts/{font_name}",
    ]

# Sentinel returned by load_font() in dev/emulator mode so draw_text()
# can distinguish small-font calls from default-font calls.
_SMALL_FONT = object()


class Canvas:
    """Abstraction layer for LED matrix canvas."""

    def __init__(self, width: int = None, height: int = None):
        # Calculate actual display dimensions from environment
        rows = int(os.getenv('LED_ROWS', 64))
        cols = int(os.getenv('LED_COLS', 64))
        chain = int(os.getenv('LED_CHAIN', 2))

        # Total width = cols * chain_length
        self.width = width if width else (cols * chain)
        self.height = height if height else rows

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

                # Color quality settings (prevent fading/contrast/flickering issues)
                options.pwm_bits = int(os.getenv('LED_PWM_BITS', 11))  # Higher = better color depth
                options.pwm_lsb_nanoseconds = int(os.getenv('LED_PWM_LSB_NANOSECONDS', 200))  # Higher = softer/smoother
                options.limit_refresh_rate_hz = int(os.getenv('LED_LIMIT_REFRESH', 0))  # 0 = no limit

                # Flickering reduction settings
                options.pwm_dither_bits = int(os.getenv('LED_PWM_DITHER_BITS', 0))  # 0 = no dither
                options.scan_mode = int(os.getenv('LED_SCAN_MODE', 1))  # 0 = progressive, 1 = interlaced
                options.row_address_type = int(os.getenv('LED_ROW_ADDRESS_TYPE', 0))  # 0 = default

                rgb_sequence = os.getenv('LED_RGB_SEQUENCE', 'RGB')
                if rgb_sequence:
                    options.led_rgb_sequence = rgb_sequence

                # Start with low brightness to prevent power surge on startup
                self._target_brightness = options.brightness
                startup_brightness = int(os.getenv('LED_STARTUP_BRIGHTNESS', 10))
                ramp_time = float(os.getenv('LED_RAMP_TIME', 2.0))
                options.brightness = startup_brightness

                self._matrix = RGBMatrix(options=options)
                self._canvas = self._matrix.CreateFrameCanvas()

                # Gradually ramp up brightness to prevent Pi reboot
                import time
                brightness_steps = max(1, (self._target_brightness - startup_brightness) // 5)
                step_delay = ramp_time / brightness_steps if brightness_steps > 0 else 0

                for brightness in range(startup_brightness, self._target_brightness + 1, 5):
                    self._matrix.brightness = brightness
                    time.sleep(step_delay)
            except ImportError:
                print("Warning: rgbmatrix not available, using emulator mode")
                self._dev_mode = True

        if self._dev_mode:
            # Development mode - use emulator or mock
            try:
                from RGBMatrixEmulator import RGBMatrix, RGBMatrixOptions
                options = RGBMatrixOptions()
                options.rows = self.height
                options.cols = self.width
                self._matrix = RGBMatrix(options=options)
                self._canvas = self._matrix.CreateFrameCanvas()
            except ImportError:
                # Mock canvas for testing without emulator
                self._canvas = MockCanvas(self.width, self.height)

        # Pixel capture buffers for web UI preview
        self._frame_buffer = [[(0, 0, 0)] * self.width for _ in range(self.height)]
        self._display_buffer = [[(0, 0, 0)] * self.width for _ in range(self.height)]

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int):
        """Set a single pixel."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._canvas.SetPixel(x, y, r, g, b)
            self._frame_buffer[y][x] = (r, g, b)

    def clear(self):
        """Clear the canvas."""
        self._canvas.Clear()
        self._frame_buffer = [[(0, 0, 0)] * self.width for _ in range(self.height)]

    def load_font(self, font_name: str = "7x13.bdf"):
        """Load a specific BDF font."""
        if self._dev_mode:
            return _SMALL_FONT  # sentinel: signals small-font rendering in preview

        try:
            from rgbmatrix import graphics
            font = graphics.Font()
            for path in _font_paths(font_name):
                if path and os.path.exists(path):
                    try:
                        font.LoadFont(path)
                        return font
                    except Exception:
                        continue
        except ImportError:
            pass
        return None

    def draw_text(self, x: int, y: int, text: str, r: int, g: int, b: int, font=None):
        """Draw text on canvas."""
        # True when a small font (5x7) was requested vs the default 7x13.
        # On hardware: font is a real graphics.Font object.
        # In dev mode: font is the _SMALL_FONT sentinel returned by load_font().
        small = font is not None

        if not self._dev_mode and hasattr(self._canvas, 'SetPixel'):
            from rgbmatrix import graphics
            # Resolve default font; strip the dev-mode sentinel if it somehow arrives
            if font is None or font is _SMALL_FONT:
                font = graphics.Font()
                loaded = False
                for path in _font_paths("7x13.bdf"):
                    if path and os.path.exists(path):
                        try:
                            font.LoadFont(path)
                            loaded = True
                            break
                        except Exception:
                            continue

                if not loaded:
                    # Last resort: search the project tree for any BDF font
                    import glob
                    bdf_fonts = (
                        glob.glob(str(_PROJECT_ROOT / "*" / "fonts" / "*.bdf")) +
                        glob.glob(str(_PROJECT_ROOT / "*" / "*" / "fonts" / "*.bdf"))
                    )
                    if bdf_fonts:
                        try:
                            font.LoadFont(bdf_fonts[0])
                        except Exception:
                            pass

            color = graphics.Color(r, g, b)
            result = graphics.DrawText(self._canvas, font, x, y, color, text)
            self._draw_text_to_buffer(x, y, text, r, g, b, small=small)
            return result
        else:
            # Mock implementation
            self._draw_text_to_buffer(x, y, text, r, g, b, small=small)
            return len(text) * 6

    def _draw_text_to_buffer(self, x: int, y: int, text: str, r: int, g: int, b: int, small: bool = False):
        """Render text into _frame_buffer for web UI preview using Pillow.

        small=True  → mirrors the 5x7 BDF font (size 7, baseline offset 6)
        small=False → mirrors the 7x13 BDF font (size 11, baseline offset 11)
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            pil_size = 7 if small else 11
            baseline_offset = 6 if small else 11
            try:
                # Pillow >= 10 accepts a size parameter
                pil_font = ImageFont.load_default(size=pil_size)
            except TypeError:
                pil_font = ImageFont.load_default()
            # rgbmatrix DrawText y is the baseline; Pillow draw.text y is the top.
            top = y - baseline_offset
            # Render to a 1-bit image so Pillow uses no anti-aliasing —
            # every pixel is either fully on or fully off, giving crisp
            # pixel-art text identical to the BDF bitmap fonts on hardware.
            mask = Image.new('1', (self.width, self.height), 0)
            draw = ImageDraw.Draw(mask)
            draw.text((x, top), text, fill=1, font=pil_font)
            pixels = mask.load()
            for py in range(self.height):
                for px in range(self.width):
                    if pixels[px, py]:
                        self._frame_buffer[py][px] = (r, g, b)
        except Exception:
            pass

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
        # Snapshot completed frame for web preview
        self._display_buffer = [row[:] for row in self._frame_buffer]

    def get_frame_png(self, scale: int = 6) -> bytes:
        """Return a scaled PNG of the current display buffer for web preview."""
        from PIL import Image
        import io
        img = Image.new('RGB', (self.width, self.height))
        img.putdata([pixel for row in self._display_buffer for pixel in row])
        scaled = img.resize((self.width * scale, self.height * scale), Image.NEAREST)
        buf = io.BytesIO()
        scaled.save(buf, format='PNG')
        return buf.getvalue()


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
