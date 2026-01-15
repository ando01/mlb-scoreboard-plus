# 🚀 Quick Start Guide

Get your improved MLB LED Scoreboard up and running in minutes!

## 📦 What You Just Got

A completely rebuilt MLB scoreboard with:
- **Real-time animations** - Smooth score changes, runners, celebrations
- **Web-based config** - No more JSON file editing!
- **Better performance** - 30 FPS, async architecture
- **Multiple modes** - Live games, stats, standings
- **Auto-rotation** - Cycles through games automatically

## 🎯 Installation (5 Minutes)

### On your Raspberry Pi:

```bash
# 1. Run the installer
./install.sh

# 2. Configure your settings
nano .env
# Change FAVORITE_TEAM to your team (e.g., NYY, BOS, LAD)
# Adjust LED_BRIGHTNESS if needed (0-100)

# 3. Start it up!
source venv/bin/activate
python3 main.py --web-ui
```

That's it! Your scoreboard is now running.

## 🌐 Web Interface

Open a browser and go to:
```
http://[your-raspberry-pi-ip]:8080
```

From here you can:
- ✅ See all today's games in real-time
- ✅ Switch display modes instantly
- ✅ Change settings without editing files
- ✅ Monitor scoreboard status

## 🎮 Basic Controls

### Display Modes
The scoreboard has three modes that auto-rotate:

1. **Live Game** - Shows full game details with animations
   - Team scores with flashing on score changes
   - Baseball diamond with animated runners
   - Ball-strike-out count
   - Current batter/pitcher info
   - Last play description

2. **Detailed Stats** - Player statistics
   - Batter: AVG, HR, RBI
   - Pitcher: ERA, SO
   - Season stats

3. **Standings** - Division rankings
   - Team records
   - Win percentage
   - Games behind

### Manual Mode Switching
Use the web UI or stop the app and restart with:
```bash
python3 main.py --web-ui
# Then use web interface to switch modes
```

## ⚙️ Quick Settings

### Edit .env for hardware settings:
```bash
LED_BRIGHTNESS=60        # Lower to save power, higher for outdoor
LED_ROWS=64             # Your matrix row count
LED_COLS=128            # Your matrix column count
FAVORITE_TEAM=NYY       # Three-letter team code
```

### Edit config/default_config.json for display settings:
```json
{
  "display": {
    "rotation_interval": 15,  // Seconds between rotations
    "default_mode": "live_game"
  },
  "animations": {
    "enabled": true,          // Turn off for performance
    "transition_speed": "normal"  // slow, normal, fast
  }
}
```

## 🎨 What Makes This Better?

Compared to the original mlb-led-scoreboard:

### 1. Beautiful Animations
- Scores flash when they change
- Runners animate around the bases
- "LIVE" indicator pulses
- Smooth transitions between displays

### 2. Web Configuration
- No more SSH and nano!
- Change settings from your phone
- See live preview of games
- Real-time status monitoring

### 3. Smarter Data Management
- Caches API responses (less API load)
- Prioritizes your favorite team
- Shows live games first
- Handles API failures gracefully

### 4. Better Performance
- 30 FPS rendering (vs ~15 FPS)
- Async architecture (no blocking)
- Lower CPU usage
- Faster startup

### 5. More Reliable
- Auto-recovery from errors
- Connection retry logic
- Graceful degradation
- Health monitoring

## 🔥 Pro Tips

1. **Favorite Team Priority** - Set your FAVORITE_TEAM in .env and it will always show if they're playing live

2. **Save Power** - Lower LED_BRIGHTNESS to 40-50 for indoor use, saves power and still looks great

3. **Multiple Games** - The scoreboard auto-rotates through all games every 15 seconds (configurable)

4. **Remote Access** - Access the web UI from any device on your network

5. **Auto-Start** - The installer can set up systemd service for automatic startup on boot

6. **Development Mode** - Set DEV_MODE=true to test without hardware

## 🐛 Common Issues

**Scoreboard not showing anything?**
- Check power supply (needs 4A+ for full brightness)
- Run with sudo: `sudo python3 main.py --web-ui`
- Check GPIO wiring

**No games showing?**
- Make sure it's baseball season! (April-October usually)
- Check internet connection
- Look for errors in terminal

**Web UI not loading?**
- Check Pi's IP address: `hostname -I`
- Make sure port 8080 is not blocked
- Try: `http://raspberrypi.local:8080`

**Performance issues?**
- Lower brightness
- Disable animations in config
- Use Raspberry Pi 4 or 5 for best performance

## 📚 Learn More

- **README.md** - Full documentation
- **config/default_config.json** - All configuration options
- **Web UI** - Live game data and status

## 🎉 Enjoy!

You now have a modern, beautiful MLB scoreboard with animations and easy configuration.

Watch it during game day and enjoy the smooth animations when your team scores! ⚾

---

**Need help?** Check the README.md or open an issue on GitHub.
