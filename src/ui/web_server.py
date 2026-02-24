"""FastAPI web server for configuration UI."""
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
import json

from ..models.config import AppConfig
from ..utils.config_loader import load_config, save_config
from ..api.data_fetcher import DataFetcher

app = FastAPI(title="MLB LED Scoreboard API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
scoreboard_instance = None
data_fetcher_instance: Optional[DataFetcher] = None


def set_scoreboard(scoreboard):
    """Set the scoreboard instance."""
    global scoreboard_instance, data_fetcher_instance
    scoreboard_instance = scoreboard
    data_fetcher_instance = scoreboard.data_fetcher


@app.get("/")
async def read_root():
    """Serve the web UI."""
    base_dir = Path(__file__).parent.parent.parent
    html_file = base_dir / "templates" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse(content="<h1>MLB Scoreboard Web UI</h1><p>Configure your scoreboard below.</p>")


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    config = load_config()
    return config.model_dump()


@app.post("/api/config")
async def update_config(config_data: dict):
    """Update configuration."""
    try:
        config = AppConfig(**config_data)
        save_config(config)

        # Update scoreboard if running
        if scoreboard_instance:
            scoreboard_instance.config = config

        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/games")
async def get_games():
    """Get current games."""
    if data_fetcher_instance:
        games = data_fetcher_instance.get_games()
        return [game.model_dump() for game in games]
    return []


@app.get("/api/standings")
async def get_standings():
    """Get current standings."""
    if data_fetcher_instance:
        standings = data_fetcher_instance.get_standings()
        return [entry.model_dump() for entry in standings]
    return []


@app.post("/api/mode")
async def set_mode(mode_data: dict):
    """Set display mode."""
    mode = mode_data.get("mode")
    if not mode:
        raise HTTPException(status_code=400, detail="Mode is required")

    if scoreboard_instance:
        scoreboard_instance.set_mode(mode)
        return {"status": "success", "message": f"Mode set to {mode}"}

    raise HTTPException(status_code=500, detail="Scoreboard not running")


@app.get("/api/status")
async def get_status():
    """Get scoreboard status."""
    if scoreboard_instance:
        return {
            "running": scoreboard_instance.running,
            "current_mode": scoreboard_instance.current_mode,
            "season_mode": scoreboard_instance.season_mode,
            "matrix_enabled": scoreboard_instance.matrix_enabled,
            "simulation_mode": data_fetcher_instance.simulate if data_fetcher_instance else False,
            "games_count": len(data_fetcher_instance.get_games()) if data_fetcher_instance else 0,
            "refresh_interval": data_fetcher_instance.refresh_interval if data_fetcher_instance else 5,
            "pinned_game_id": data_fetcher_instance.pinned_game_id if data_fetcher_instance else None,
        }
    return {"running": False}


@app.get("/api/display/preview")
async def get_display_preview(scale: int = 6):
    """Return a scaled PNG snapshot of the current display frame."""
    scale = max(1, min(scale, 12))
    if scoreboard_instance and hasattr(scoreboard_instance, 'canvas'):
        try:
            png_bytes = scoreboard_instance.canvas.get_frame_png(scale=scale)
        except Exception:
            png_bytes = _black_png(scale)
    else:
        png_bytes = _black_png(scale)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


def _black_png(scale: int = 6) -> bytes:
    """Generate a solid black PNG at the default display dimensions."""
    from PIL import Image
    import io
    import os
    rows = int(os.getenv('LED_ROWS', 64))
    cols = int(os.getenv('LED_COLS', 64))
    chain = int(os.getenv('LED_CHAIN', 2))
    w, h = cols * chain, rows
    img = Image.new('RGB', (w * scale, h * scale), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@app.get("/api/display/settings")
async def get_display_settings():
    """Get current display settings from environment."""
    import os

    return {
        "pwm_lsb_nanoseconds": int(os.getenv('LED_PWM_LSB_NANOSECONDS', 200)),
        "pwm_bits": int(os.getenv('LED_PWM_BITS', 11)),
        "gpio_slowdown": int(os.getenv('LED_GPIO_SLOWDOWN', 4)),
        "brightness": int(os.getenv('LED_BRIGHTNESS', 30))
    }


@app.post("/api/brightness")
async def set_brightness(data: dict):
    """Set LED brightness in real-time."""
    brightness = data.get("brightness")
    if brightness is None or not (0 <= brightness <= 100):
        raise HTTPException(status_code=400, detail="Brightness must be 0-100")

    if scoreboard_instance and hasattr(scoreboard_instance.canvas, '_matrix'):
        try:
            scoreboard_instance.canvas._matrix.brightness = int(brightness)
            return {"status": "success", "brightness": brightness}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to set brightness: {str(e)}")

    raise HTTPException(status_code=500, detail="Scoreboard not running")


@app.post("/api/display/settings")
async def set_display_settings(data: dict):
    """Set display quality settings in real-time (requires restart for some settings)."""
    import os

    # These settings require restart
    pwm_lsb = data.get("pwm_lsb_nanoseconds")
    pwm_bits = data.get("pwm_bits")
    gpio_slowdown = data.get("gpio_slowdown")

    # Update environment variables (will take effect on next restart)
    env_file = os.path.join(os.path.dirname(__file__), '..', '..', '.env')

    try:
        # Read existing .env
        env_vars = {}
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value

        # Update values
        if pwm_lsb is not None:
            env_vars['LED_PWM_LSB_NANOSECONDS'] = str(pwm_lsb)
        if pwm_bits is not None:
            env_vars['LED_PWM_BITS'] = str(pwm_bits)
        if gpio_slowdown is not None:
            env_vars['LED_GPIO_SLOWDOWN'] = str(gpio_slowdown)

        # Write back to .env
        with open(env_file, 'w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        return {
            "status": "success",
            "message": "Settings saved. Restart scoreboard to apply changes.",
            "settings": {
                "pwm_lsb_nanoseconds": pwm_lsb,
                "pwm_bits": pwm_bits,
                "gpio_slowdown": gpio_slowdown
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@app.post("/api/restart")
async def restart_scoreboard():
    """Restart the scoreboard application."""
    import os
    import sys
    import signal
    try:
        # Get the current process ID
        pid = os.getpid()
        # Schedule a restart by sending SIGHUP or just exit and let systemd/supervisor restart
        # For now, we'll use os.execv with the correct arguments
        args = [sys.executable] + sys.argv
        os.execv(sys.executable, args)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart: {str(e)}")


@app.post("/api/season-mode")
async def set_season_mode(data: dict):
    """Set season mode (on/off-season)."""
    mode = data.get("mode")
    if mode not in ["on", "off"]:
        raise HTTPException(status_code=400, detail="Mode must be 'on' or 'off'")

    if scoreboard_instance:
        # Set season mode in scoreboard
        scoreboard_instance.season_mode = mode

        if mode == "off":
            # Switch to news mode
            scoreboard_instance.set_mode("news")
        else:
            # Switch back to live game mode
            scoreboard_instance.set_mode("live_game")

        return {
            "status": "success",
            "mode": mode,
            "message": f"Switched to {mode}-season mode"
        }

    raise HTTPException(status_code=500, detail="Scoreboard not running")


@app.post("/api/matrix/toggle")
async def toggle_matrix(data: dict):
    """Toggle LED matrix on/off."""
    enabled = data.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="Enabled state is required")

    if scoreboard_instance:
        scoreboard_instance.matrix_enabled = enabled
        # Render loop will handle clearing/displaying automatically

        return {
            "status": "success",
            "enabled": enabled,
            "message": f"LED matrix turned {'ON' if enabled else 'OFF'}"
        }

    raise HTTPException(status_code=500, detail="Scoreboard not running")


@app.get("/api/refresh-interval")
async def get_refresh_interval():
    """Get the current data refresh interval in seconds."""
    if data_fetcher_instance:
        return {"refresh_interval": data_fetcher_instance.refresh_interval}
    return {"refresh_interval": 5}


@app.post("/api/refresh-interval")
async def set_refresh_interval(data: dict):
    """Set the data refresh interval in seconds (5-60)."""
    interval = data.get("interval")
    if interval is None or not isinstance(interval, int) or not (5 <= interval <= 60):
        raise HTTPException(status_code=400, detail="Interval must be an integer between 5 and 60")

    if data_fetcher_instance:
        data_fetcher_instance.refresh_interval = interval
        return {"status": "success", "refresh_interval": interval}

    raise HTTPException(status_code=500, detail="Scoreboard not running")


@app.post("/api/games/pin")
async def pin_game(data: dict):
    """Pin a specific game to the scoreboard display. Send game_id=null to auto-select."""
    game_id = data.get("game_id")  # None = auto-select
    if data_fetcher_instance:
        data_fetcher_instance.set_pinned_game(game_id)
        return {"status": "success", "pinned_game_id": game_id}
    raise HTTPException(status_code=500, detail="Scoreboard not running")

@app.post("/api/simulation/toggle")
async def toggle_simulation(data: dict):
    """Toggle simulation mode on/off."""
    enabled = data.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="Enabled state is required")

    if data_fetcher_instance:
        data_fetcher_instance.set_simulation_mode(enabled)
        return {
            "status": "success",
            "enabled": enabled,
            "message": f"Simulation mode {'enabled' if enabled else 'disabled'}"
        }

    raise HTTPException(status_code=500, detail="Scoreboard not running")


@app.get("/api/teams")
async def get_all_teams():
    """Get list of all MLB teams."""
    teams = [
        {"abbr": "NYY", "name": "New York Yankees"},
        {"abbr": "BOS", "name": "Boston Red Sox"},
        {"abbr": "TB", "name": "Tampa Bay Rays"},
        {"abbr": "TOR", "name": "Toronto Blue Jays"},
        {"abbr": "BAL", "name": "Baltimore Orioles"},
        {"abbr": "CLE", "name": "Cleveland Guardians"},
        {"abbr": "MIN", "name": "Minnesota Twins"},
        {"abbr": "CHW", "name": "Chicago White Sox"},
        {"abbr": "DET", "name": "Detroit Tigers"},
        {"abbr": "KC", "name": "Kansas City Royals"},
        {"abbr": "HOU", "name": "Houston Astros"},
        {"abbr": "TEX", "name": "Texas Rangers"},
        {"abbr": "SEA", "name": "Seattle Mariners"},
        {"abbr": "LAA", "name": "Los Angeles Angels"},
        {"abbr": "OAK", "name": "Oakland Athletics"},
        {"abbr": "ATL", "name": "Atlanta Braves"},
        {"abbr": "PHI", "name": "Philadelphia Phillies"},
        {"abbr": "NYM", "name": "New York Mets"},
        {"abbr": "MIA", "name": "Miami Marlins"},
        {"abbr": "WSH", "name": "Washington Nationals"},
        {"abbr": "MIL", "name": "Milwaukee Brewers"},
        {"abbr": "STL", "name": "St. Louis Cardinals"},
        {"abbr": "CHC", "name": "Chicago Cubs"},
        {"abbr": "CIN", "name": "Cincinnati Reds"},
        {"abbr": "PIT", "name": "Pittsburgh Pirates"},
        {"abbr": "LAD", "name": "Los Angeles Dodgers"},
        {"abbr": "SFG", "name": "San Francisco Giants"},
        {"abbr": "SD", "name": "San Diego Padres"},
        {"abbr": "ARI", "name": "Arizona Diamondbacks"},
        {"abbr": "COL", "name": "Colorado Rockies"},
    ]
    return teams


@app.post("/api/teams/selected")
async def set_selected_teams(data: dict):
    """Set teams to display and cycle through."""
    teams = data.get("teams", [])
    if not teams or not isinstance(teams, list):
        raise HTTPException(status_code=400, detail="Teams must be a non-empty list")

    if len(teams) < 1 or len(teams) > 5:
        raise HTTPException(status_code=400, detail="Must select 1-5 teams")

    if scoreboard_instance:
        # Update config
        config = load_config()
        config.teams.preferred_teams = teams
        config.teams.display_all = False
        favorite = data.get("favorite")
        if favorite:
            config.teams.favorite = favorite
        save_config(config)

        # Update running scoreboard
        scoreboard_instance.config = config
        if data_fetcher_instance:
            data_fetcher_instance.config = config

        return {"status": "success", "teams": teams, "favorite": config.teams.favorite}

    raise HTTPException(status_code=500, detail="Scoreboard not running")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    try:
        while True:
            # Send status updates
            if data_fetcher_instance:
                games = data_fetcher_instance.get_games()
                await websocket.send_json({
                    "type": "games",
                    "data": [game.model_dump() for game in games]
                })

            await asyncio.sleep(5)  # Update every 5 seconds
    except Exception as e:
        print(f"WebSocket error: {e}")


def run_server(scoreboard, host: str = "0.0.0.0", port: int = 8080):
    """Run the web server."""
    import uvicorn

    set_scoreboard(scoreboard)

    # Mount static files
    base_dir = Path(__file__).parent.parent.parent
    static_dir = base_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    uvicorn.run(app, host=host, port=port)
