"""Game data simulator for testing and off-season."""
import random
from datetime import datetime, timedelta
from typing import List
from ..models.game import (
    LiveGameData, GameState, Team, Inning, Count,
    BaseRunner, Play, PlayerStats, StandingsEntry
)


class GameSimulator:
    """Simulates live game data for testing."""

    def __init__(self):
        self.teams = [
            ("NYY", "New York Yankees"),
            ("BOS", "Boston Red Sox"),
            ("LAD", "Los Angeles Dodgers"),
            ("SFG", "San Francisco Giants"),
            ("CHC", "Chicago Cubs"),
            ("STL", "St. Louis Cardinals"),
            ("ATL", "Atlanta Braves"),
            ("HOU", "Houston Astros"),
        ]

        self.player_names = [
            "Aaron Judge", "Mookie Betts", "Freddie Freeman", "Jose Altuve",
            "Ronald Acuña Jr.", "Juan Soto", "Shohei Ohtani", "Mike Trout",
            "Bryce Harper", "Fernando Tatis Jr.", "Pete Alonso", "Vladimir Guerrero Jr."
        ]

        self.pitcher_names = [
            "Gerrit Cole", "Sandy Alcantara", "Justin Verlander", "Corbin Burnes",
            "Dylan Cease", "Shane McClanahan", "Spencer Strider", "Zack Wheeler"
        ]

        self.games: List[LiveGameData] = []
        self.update_counter = 0
        self._initialize_games()
        print(f"[SIMULATOR] Initialized with {len(self.games)} games")

    def _initialize_games(self):
        """Create initial simulated games."""
        # Create 3-4 games with different states
        num_games = random.randint(3, 4)

        for i in range(num_games):
            home_team_idx = random.randint(0, len(self.teams) - 1)
            away_team_idx = (home_team_idx + i + 1) % len(self.teams)

            home_abbr, home_name = self.teams[home_team_idx]
            away_abbr, away_name = self.teams[away_team_idx]

            # Vary game states
            if i == 0:
                state = GameState.LIVE
                inning_num = random.randint(3, 7)
            elif i == 1:
                state = GameState.LIVE
                inning_num = random.randint(1, 9)
            elif i == 2:
                state = GameState.FINAL
                inning_num = 9
            else:
                state = GameState.PREVIEW
                inning_num = 1

            game = self._create_game(
                game_id=1000 + i,
                home_abbr=home_abbr,
                home_name=home_name,
                away_abbr=away_abbr,
                away_name=away_name,
                state=state,
                inning_num=inning_num
            )

            self.games.append(game)

    def _create_game(self, game_id: int, home_abbr: str, home_name: str,
                     away_abbr: str, away_name: str, state: GameState,
                     inning_num: int) -> LiveGameData:
        """Create a simulated game."""

        if state == GameState.PREVIEW:
            # Preview game
            home_score = 0
            away_score = 0
            current_batter = None
            current_pitcher = None
            prob_home = random.choice(self.pitcher_names)
            prob_away = random.choice(self.pitcher_names)
            last_play = None
            runners = BaseRunner()
            count = Count()
        else:
            # Live or final game
            home_score = random.randint(0, 8)
            away_score = random.randint(0, 8)

            if state == GameState.FINAL:
                # Make sure there's a winner
                if home_score == away_score:
                    home_score += 1

            # Current players
            batter = random.choice(self.player_names)
            pitcher = random.choice(self.pitcher_names)

            current_batter = PlayerStats(
                name=batter,
                avg=f".{random.randint(220, 340)}",
                hr=random.randint(5, 40),
                rbi=random.randint(20, 100)
            )

            current_pitcher = PlayerStats(
                name=pitcher,
                era=f"{random.randint(2, 5)}.{random.randint(10, 99)}",
                so=random.randint(50, 200)
            )

            prob_home = None
            prob_away = None

            # Runners
            has_first = random.random() > 0.7
            has_second = random.random() > 0.8
            has_third = random.random() > 0.85

            runners = BaseRunner(
                first=random.choice(self.player_names) if has_first else None,
                second=random.choice(self.player_names) if has_second else None,
                third=random.choice(self.player_names) if has_third else None
            )

            # Count
            count = Count(
                balls=random.randint(0, 3),
                strikes=random.randint(0, 2),
                outs=random.randint(0, 2)
            )

            # Last play
            play_types = [
                ("Single to center field", "single", False),
                ("Strikeout swinging", "strikeout", False),
                ("Home run to left field!", "home_run", True),
                ("Ground out to second base", "groundout", False),
                ("Double to right-center", "double", False),
                ("Flyout to center field", "flyout", False),
                ("RBI single to left!", "single", True),
            ]

            play_desc, play_event, is_scoring = random.choice(play_types)
            last_play = Play(
                description=play_desc,
                event=play_event,
                is_scoring_play=is_scoring,
                rbi=random.randint(1, 3) if is_scoring else 0
            )

        home_team = Team(
            id=home_abbr.__hash__(),
            name=home_name,
            abbreviation=home_abbr,
            score=home_score,
            hits=random.randint(home_score, home_score + 8),
            errors=random.randint(0, 2),
            is_winner=home_score > away_score if state == GameState.FINAL else False
        )

        away_team = Team(
            id=away_abbr.__hash__(),
            name=away_name,
            abbreviation=away_abbr,
            score=away_score,
            hits=random.randint(away_score, away_score + 8),
            errors=random.randint(0, 2),
            is_winner=away_score > home_score if state == GameState.FINAL else False
        )

        inning_half = "top" if random.random() > 0.5 else "bottom"
        inning = Inning(
            num=inning_num,
            ordinal=self._get_ordinal(inning_num),
            half=inning_half
        )

        start_time = datetime.now() - timedelta(hours=2)

        # Add pitch information for live games
        pitch_types = ["FF", "SL", "CH", "CU", "SI", "FC", "KC"]
        last_pitch_type = random.choice(pitch_types) if state == GameState.LIVE else None
        last_pitch_speed = round(random.uniform(88.0, 99.0), 1) if state == GameState.LIVE else None
        pitch_count = random.randint(5, 35) if state == GameState.LIVE else None
        show_pitch_result = False  # Start with showing pitch count

        return LiveGameData(
            game_id=game_id,
            state=state,
            start_time=start_time,
            inning=inning,
            count=count,
            runners=runners,
            home_team=home_team,
            away_team=away_team,
            current_batter=current_batter,
            current_pitcher=current_pitcher,
            last_play=last_play,
            probable_pitcher_home=prob_home,
            probable_pitcher_away=prob_away,
            last_pitch_type=last_pitch_type,
            last_pitch_speed=last_pitch_speed,
            pitch_count=pitch_count,
            show_pitch_result=show_pitch_result
        )

    def _get_ordinal(self, num: int) -> str:
        """Get ordinal string for inning number."""
        if 10 <= num % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(num % 10, 'th')
        return f"{num}{suffix}"

    def update_games(self):
        """Simulate game updates (scores, plays, etc.)."""
        self.update_counter += 1

        # Update every few calls to simulate realistic pace
        if self.update_counter % 5 != 0:
            return

        for game in self.games:
            if game.state != GameState.LIVE:
                continue

            # Randomly update game state
            action = random.random()

            if action < 0.15:  # 15% chance - score change
                scoring_team = random.choice(['home', 'away'])
                if scoring_team == 'home':
                    game.home_team.score += random.randint(1, 2)
                    game.home_team.hits += 1
                else:
                    game.away_team.score += random.randint(1, 2)
                    game.away_team.hits += 1

                # Update last play to scoring play
                play_types = [
                    "Home run to deep center!",
                    "RBI double to the gap!",
                    "RBI single up the middle!",
                    "Sacrifice fly to left, runner scores!"
                ]
                game.last_play = Play(
                    description=random.choice(play_types),
                    event="scoring_play",
                    is_scoring_play=True,
                    rbi=random.randint(1, 2)
                )

                # Reset pitch count for new batter after scoring play
                game.pitch_count = 0
                game.show_pitch_result = False

            elif action < 0.35:  # 20% chance - count change (pitch thrown)
                game.count.balls = random.randint(0, 3)
                game.count.strikes = random.randint(0, 2)

                # Update pitch info and increment pitch count
                pitch_types = ["FF", "SL", "CH", "CU", "SI", "FC", "KC"]
                game.last_pitch_type = random.choice(pitch_types)
                game.last_pitch_speed = round(random.uniform(88.0, 99.0), 1)
                game.pitch_count = (game.pitch_count or 0) + 1

                # Show pitch result after pitch is thrown
                game.show_pitch_result = True

            elif action < 0.40:  # 5% chance - pitcher ready (between pitches)
                # Toggle back to showing pitch count
                game.show_pitch_result = False

            elif action < 0.45:  # 10% chance - runner change
                game.runners.first = random.choice(self.player_names) if random.random() > 0.5 else None
                game.runners.second = random.choice(self.player_names) if random.random() > 0.7 else None
                game.runners.third = random.choice(self.player_names) if random.random() > 0.8 else None

            elif action < 0.55:  # 10% chance - out recorded
                if game.count.outs >= 3:
                    # End-of-inning screen was showing; now start the new half
                    game.count.outs = 0
                    game.count.balls = 0
                    game.count.strikes = 0
                    game.next_batters = []
                    game.next_batter_positions = []
                else:
                    game.count.outs += 1
                    game.pitch_count = 0
                    game.show_pitch_result = False

                    if game.count.outs == 3:
                        # Inning change — populate next-up display before resetting
                        game.runners = BaseRunner()

                        # Pick 3 consecutive batters starting at a random lineup spot
                        start_pos = random.randint(0, len(self.player_names) - 4)
                        game.next_batters = list(self.player_names[start_pos:start_pos + 3])
                        game.next_batter_positions = list(range(start_pos + 1, start_pos + 4))

                        if game.inning.half == "top":
                            game.inning.half = "bottom"
                        else:
                            game.inning.half = "top"
                            game.inning.num = min(game.inning.num + 1, 9)
                            game.inning.ordinal = self._get_ordinal(game.inning.num)

                    game.last_play = Play(
                        description=random.choice([
                            "Strikeout looking",
                            "Ground out to shortstop",
                            "Flyout to center field",
                            "Pop out to first base"
                        ]),
                        event="out",
                        is_scoring_play=False
                    )

            # Advance to final state if late inning
            if game.inning.num >= 9 and game.inning.half == "bottom":
                if random.random() > 0.9:  # Small chance to end game
                    game.state = GameState.FINAL
                    game.count = Count(balls=0, strikes=0, outs=3)
                    game.runners = BaseRunner()
                    # Ensure winner
                    if game.home_team.score <= game.away_team.score:
                        game.home_team.score = game.away_team.score + 1
                    game.home_team.is_winner = True

    def get_games(self) -> List[LiveGameData]:
        """Get current simulated games."""
        self.update_games()
        return self.games

    def get_standings(self) -> List[StandingsEntry]:
        """Get simulated standings."""
        standings = []

        # AL East
        al_east = [
            ("New York Yankees", "NYY", 92, 70, ".568", "-"),
            ("Tampa Bay Rays", "TB", 90, 72, ".556", "2.0"),
            ("Toronto Blue Jays", "TOR", 85, 77, ".525", "7.0"),
            ("Baltimore Orioles", "BAL", 83, 79, ".512", "9.0"),
            ("Boston Red Sox", "BOS", 78, 84, ".481", "14.0"),
        ]

        # NL West
        nl_west = [
            ("Los Angeles Dodgers", "LAD", 100, 62, ".617", "-"),
            ("San Diego Padres", "SD", 89, 73, ".549", "11.0"),
            ("San Francisco Giants", "SFG", 81, 81, ".500", "19.0"),
            ("Arizona Diamondbacks", "ARI", 74, 88, ".457", "26.0"),
            ("Colorado Rockies", "COL", 68, 94, ".420", "32.0"),
        ]

        for name, abbr, w, l, pct, gb in al_east:
            standings.append(StandingsEntry(
                team_name=name,
                team_abbr=abbr,
                wins=w,
                losses=l,
                pct=pct,
                gb=gb,
                division="AL East"
            ))

        for name, abbr, w, l, pct, gb in nl_west:
            standings.append(StandingsEntry(
                team_name=name,
                team_abbr=abbr,
                wins=w,
                losses=l,
                pct=pct,
                gb=gb,
                division="NL West"
            ))

        return standings
