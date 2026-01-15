# ⚾ MLB LED Scoreboard v2.0

A modern, feature-rich MLB LED scoreboard application for Raspberry Pi with LED matrix displays. Built from the ground up with performance, reliability, and beautiful animations in mind.

## ✨ Features

### 🎯 Core Features
- **Real-time MLB game data** - Live scores, play-by-play updates, and game status
- **Smooth animations** - Animated score changes, runner movements, and celebrations
- **Multiple display modes**:
  - Live Game - Full game details with runners, count, and outs
  - Detailed Stats - Current batter/pitcher statistics
  - Standings - Division standings with records
- **Web-based configuration** - Modern web UI for easy setup and control
- **Auto-rotation** - Automatically cycle through games and display modes
- **Smart caching** - Efficient API usage with intelligent data caching

### 🎨 Visual Enhancements
- Animated runners on base paths
- Pulsing "LIVE" indicator for active games
- Score change celebrations with flashing
- Baseball diamond visualization
- Ball-strike-out indicators
- Color-coded game states

### 🚀 Performance & Reliability
- Async/await architecture for smooth 30 FPS rendering
- Automatic error recovery
- Graceful API failure handling
- Low memory footprint
- Optimized for Raspberry Pi

## 📋 Requirements

### Hardware
- Raspberry Pi (3B+, 4, or 5 recommended)
- Adafruit RGB Matrix HAT or equivalent
- 64x64 LED matrix panels (2x for 128x64 display)
- 5V power supply (4A+ recommended)

### Software
- Raspberry Pi OS (Bullseye or newer)
- Python 3.9 or higher
- Internet connection

## 🔧 Installation

### Quick Install

1. Clone this repository:
```bash
git clone https://github.com/yourusername/mlb-led-scoreboard-v2.git
cd mlb-led-scoreboard-v2
```

2. Run the installation script:
```bash
chmod +x install.sh
./install.sh
```

3. Configure your settings:
```bash
nano .env
```

4. Start the scoreboard:
```bash
source venv/bin/activate
python3 main.py --web-ui
```

### Manual Installation

1. Install system dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-dev python3-venv git
```

2. Install RGB matrix library:
```bash
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd rpi-rgb-led-matrix
make build-python PYTHON=$(which python3)
sudo make install-python PYTHON=$(which python3)
cd ..
```

3. Create virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Display Settings
LED_ROWS=64                    # LED matrix rows
LED_COLS=128                   # LED matrix columns
LED_BRIGHTNESS=60              # Brightness (0-100)
LED_GPIO_MAPPING=adafruit-hat  # GPIO mapping

# Application
FAVORITE_TEAM=NYY              # Your favorite team abbreviation
UPDATE_INTERVAL=10             # Data update interval (seconds)
ROTATION_INTERVAL=15           # Display rotation interval (seconds)

# Web UI
WEB_UI_PORT=8080              # Web interface port
WEB_UI_HOST=0.0.0.0           # Web interface host

# Development
DEV_MODE=false                 # Use emulator instead of LED matrix
```

### Configuration File (config/default_config.json)

The main configuration file allows fine-tuning of display modes, animations, and team preferences. Edit this file to customize:

- Display brightness and rotation settings
- Favorite teams and display preferences
- Enable/disable specific display modes
- Animation settings and speed
- Division standings to display

## 🎮 Usage

### Command Line Options

```bash
# Run scoreboard with web UI
python3 main.py --web-ui

# Run with simulated game data (great for off-season testing!)
python3 main.py --web-ui --simulate

# Run web UI only (for configuration)
python3 main.py --web-ui-only

# Specify custom config file
python3 main.py --config /path/to/config.json

# Custom web UI port
python3 main.py --web-ui --web-port 8888
```

### Web UI

Access the web interface at `http://[raspberry-pi-ip]:8080`

Features:
- Live game monitoring
- Display mode switching
- Configuration updates
- Real-time status
- Brightness control

### Systemd Service (Auto-start)

The installation script can set up a systemd service for automatic startup:

```bash
# Start service
sudo systemctl start mlb-scoreboard

# Stop service
sudo systemctl stop mlb-scoreboard

# Enable auto-start on boot
sudo systemctl enable mlb-scoreboard

# View logs
sudo journalctl -u mlb-scoreboard -f
```

## 🎨 Display Modes

### Live Game Mode
Shows real-time game information:
- Team abbreviations and scores
- Current inning and half
- Balls, strikes, and outs
- Runners on base (visual diamond)
- Current batter and pitcher
- Last play description

### Detailed Stats Mode
Displays detailed statistics:
- Current batter stats (AVG, HR, RBI)
- Current pitcher stats (ERA, SO)
- Season statistics
- Recent performance

### Standings Mode
Shows division standings:
- Team records (W-L)
- Winning percentage
- Games behind leader
- Highlights favorite team

## 🛠️ Architecture

### Project Structure
```
mlb-led-scoreboard-v2/
├── src/
│   ├── api/              # MLB API client and data fetcher
│   ├── models/           # Data models and configuration
│   ├── renderers/        # Display renderers and animations
│   ├── ui/               # Web interface
│   └── utils/            # Utility functions
├── config/               # Configuration files
├── templates/            # Web UI templates
├── static/               # Static assets
├── main.py               # Main entry point
└── requirements.txt      # Python dependencies
```

### Key Components

- **MLBAPIClient** - Async MLB Stats API wrapper with caching
- **DataFetcher** - Coordinates data fetching and updates
- **Canvas** - Hardware abstraction layer for LED matrix
- **Renderers** - Mode-specific display logic with animations
- **AnimationManager** - Smooth animation system
- **WebServer** - FastAPI-based configuration interface

## 🎯 Improvements Over Original

This rewrite includes significant improvements over the original mlb-led-scoreboard:

1. **Modern Architecture**
   - Async/await for non-blocking operations
   - Modular design with clear separation of concerns
   - Type hints throughout for better code quality

2. **Enhanced Animations**
   - Smooth transitions and effects
   - Animated score changes
   - Runner movement animations
   - Pulsing indicators

3. **Better Performance**
   - 30 FPS rendering
   - Smart caching reduces API calls
   - Optimized drawing routines
   - Lower CPU usage

4. **Improved UX**
   - Web-based configuration (no JSON editing!)
   - Real-time status monitoring
   - Live preview in web UI
   - Better error messages

5. **More Reliable**
   - Automatic error recovery
   - Graceful API failure handling
   - Connection retry logic
   - Health monitoring

## 🐛 Troubleshooting

### Display not working
- Check power supply (needs 4A+ for full brightness)
- Verify GPIO wiring matches your HAT
- Try different `LED_GPIO_MAPPING` values
- Run with `sudo` for GPIO access

### No games showing
- Check internet connection
- Verify MLB API is accessible
- Check date (no games on off-days)
- View logs for API errors

### Web UI not accessible
- Check firewall settings
- Verify `WEB_UI_PORT` is not in use
- Use `0.0.0.0` for `WEB_UI_HOST` to allow external access

### Performance issues
- Lower brightness to reduce power draw
- Disable animations if needed
- Increase `UPDATE_INTERVAL`
- Use faster Raspberry Pi model

## 📝 Development

### Running in Development Mode

Set `DEV_MODE=true` in `.env` to use the emulator instead of actual LED matrix:

```bash
DEV_MODE=true python3 main.py --web-ui
```

### Testing

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Original [mlb-led-scoreboard](https://github.com/MLB-LED-Scoreboard/mlb-led-scoreboard) project
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) by Henner Zeller
- [MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI) for game data
- Adafruit for excellent hardware documentation

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review troubleshooting section

---

**Enjoy your new MLB LED scoreboard! ⚾🎉**
