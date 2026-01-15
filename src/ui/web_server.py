"""FastAPI web server for configuration UI."""
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
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
            "games_count": len(data_fetcher_instance.get_games()) if data_fetcher_instance else 0
        }
    return {"running": False}


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
