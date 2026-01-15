# 🎮 Simulation Mode

Since it's the off-season, I've added a simulation mode so you can see the scoreboard in action with realistic game data!

## 🚀 Quick Start

On your Raspberry Pi, restart the scoreboard with the `--simulate` flag:

```bash
# Stop current process (Ctrl+C)

# Restart with simulation
python3 main.py --web-ui --simulate
```

## ✨ What You'll See

The simulator creates **3-4 realistic games** with:

- ✅ **Live game action** - NYY vs BOS, LAD vs SFG, etc.
- ✅ **Dynamic score updates** - Scores change every ~30 seconds
- ✅ **Runners on base** - Animated runners moving around the diamond
- ✅ **Real play-by-play** - "Home run to left!", "RBI single!", etc.
- ✅ **Ball-strike-out counts** - Updates with each pitch
- ✅ **Inning progression** - Games advance through innings
- ✅ **Multiple game states** - Preview, Live (2 games), and Final
- ✅ **Division standings** - AL East and NL West with realistic records

## 🎨 Animations You'll See

1. **Score Changes** - Watch scores flash yellow when they change
2. **Pulsing LIVE indicator** - Green dot pulses for live games
3. **Runner movements** - Yellow dots show runners on base
4. **Auto-rotation** - Cycles through games every 15 seconds

## 📊 Sample Games

The simulator creates games like:
- **Game 1 (Live)**: New York Yankees @ Boston Red Sox - 5th inning
- **Game 2 (Live)**: Los Angeles Dodgers @ San Francisco Giants - 3rd inning
- **Game 3 (Final)**: Chicago Cubs @ St. Louis Cardinals - Final
- **Game 4 (Preview)**: Atlanta Braves @ Houston Astros - Starting soon

## 🌐 Web UI with Simulation

The web interface (http://[pi-ip]:8080) will show:
- All simulated games with live scores
- Current mode and game count
- Ability to switch between display modes
- Real-time updates as games progress

## 🔄 How It Works

The simulator:
- Creates games at startup with random teams
- Updates every ~5 seconds with new plays
- Randomly generates:
  - Score changes (15% chance)
  - Strikes/balls (20% chance)
  - Runners advancing (10% chance)
  - Outs recorded (10% chance)
- Progresses through innings naturally
- Ends games when they reach 9+ innings

## 💡 Perfect For

- **Testing your setup** - See the full scoreboard in action
- **Off-season months** - No real games? No problem!
- **Development** - Test new features with live-like data
- **Demonstrations** - Show others what it looks like during game day

## 🔙 Switch Back to Real Games

When baseball season starts, just remove the `--simulate` flag:

```bash
python3 main.py --web-ui
```

The scoreboard will automatically fetch real MLB game data.

## 🎯 Environment Variable

You can also enable simulation mode via environment variable:

```bash
export SIMULATE_GAMES=true
python3 main.py --web-ui
```

Or add to your `.env` file:
```
SIMULATE_GAMES=true
```

---

**Enjoy watching the simulated games!** ⚾ When the real season starts, you'll see actual MLB data with the same beautiful animations.
