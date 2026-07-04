# World Cup Match Prediction Engine

Player-level Monte Carlo simulator for soccer matches. Instead of comparing
teams as single numbers, it matches **attackers against the actual defenders
they'll face** (left winger vs right back, striker vs center backs), converts
those battles into expected goals, then simulates the match 100,000 times to
produce win probabilities, average goals, likely scorelines, and anytime
scorer probabilities — including extra time and penalty shootouts for
knockout games.

Ships with rosters for three real 2026 Round of 16 ties:
**Argentina–Egypt, Brazil–Norway, Mexico–England.**

## Quick start

```bash
pip install numpy
python main.py                          # ARG vs EGY, 100,000 sims
python main.py --home BRA --away NOR    # any matchup
python main.py --fixtures               # all three real R16 ties
python main.py --sims 250000 --validate # more sims + math sanity check
python main.py --save                   # also write results JSON
python main.py --group-stage            # 90' only, draws stand
python main.py --neutral                # strip venue/weather/crowd effects
python main.py --list-teams
```

## How the model works

**1. Zone matchups (`soccer_sim/matchup.py`)**
The pitch is split into left / center / right attacking zones. Each player
contributes to zones based on position (a LW is the main left threat; the
overlapping LB, drifting AM, and near-post ST contribute partial weight).
Defensively it mirrors: your LW meets their RB plus covering CB and DM.
Attacking power = 40% attack + 35% creativity + 25% pace; defending power =
55% defense + 20% pace + 25% physical — all scaled by form, fitness, and
expected minutes. The attack/defense ratio in each zone becomes a chance
multiplier (elasticity 1.6, clamped 0.55–1.85).

**2. Team attack & defense scores (`soccer_sim/models.py`)**
Every team also gets an overall **attack score** and **defense score**
(0–100), printed at the top of each report. They're minutes/fitness-weighted
averages of individual attacking/defending power, position-weighted by
influence (strikers dominate the attack score; GK and center backs anchor
the defense score). Zone ratios capture the *relative* matchup; these
capture *absolute* quality — an elite attack creates more chances against
anyone, an elite defense concedes fewer against anyone. Each side's expected
goals are scaled by its attack score and the opponent's defense score
against a tournament-average baseline of 76.5 (elasticity 0.65, clamped
0.70–1.40). Injuries and cold form pull the scores down automatically.

**3. Match conditions (`soccer_sim/context.py`)**
Everything around the game, not just the players. A `MatchContext` carries
the venue and circumstances; each factor becomes a small, bounded per-team
multiplier, printed as a breakdown at the top of the report:

| Factor | Effect |
|---|---|
| Crowd size + allegiance | up to ±8% for a full partisan stadium (≈ observed home advantage) |
| Altitude | thin air boosts everyone slightly; unacclimated legs lose up to 9% |
| Heat + humidity | slows tempo; heat-adapted teams lose ~1/3 as much (roof closed = no weather) |
| Rain | slick ball, keeper errors → slightly more goals for both |
| Wind | ruins crossing/long service for both sides |
| Pitch quality | a chewed-up surface suppresses chance creation |
| Rest days + travel | short turnaround and long flights cost freshness |
| Referee style | a permissive ref favors the more physical side; whistle-happy blunts it |

The three shipped fixtures carry real venue conditions (see `CONTEXTS` in
the data file): Argentina–Egypt indoors at AT&T Stadium, Brazil–Norway in
Miami heat that Norway isn't built for, and Mexico–England at Estadio
Azteca — 2,240m altitude, 87,000 fans at 85% green, and a worn pitch.
The Azteca package alone moves Mexico from ~28% to ~33% to advance. Run
with `--neutral` to strip conditions and see the pure player-model number;
per-side totals are clamped to [0.75, 1.30] so conditions tilt the
football, never replace it.

**4. Expected goals**
`lambda = 1.28 (knockout baseline) x zone blend (27/46/27) x attack-score
x opposing-defense-score x midfield-control x opposing-GK factor x team
form x match-conditions`, clamped to [0.25, 4.0].

**5. Monte Carlo (`soccer_sim/simulator.py`)**
Goals per team per sim ~ Poisson(lambda), fully vectorized. Every goal is
assigned to a scorer via a multinomial over player weights:
`attack^1.7 x position multiplier x minutes x form x fitness`, with a bump
for penalty takers. Level knockout games play 30' of extra time at a reduced
scoring rate; still-level games go to a shootout modeled from the top five
takers' quality vs the opposing keeper.

**6. Validation (`--validate`)**
By Poisson thinning, a player with share *p* of team goals scores with
probability `1 - exp(-lambda*p)`. The flag prints this closed form next to
the Monte Carlo estimate — they should agree within ~0.5% at 100k sims,
which confirms the simulator is converging correctly.

## Updating team news (injuries, form, lineups)

Everything lives in `soccer_sim/data/worldcup2026.py`. Edit in place:

```python
Player("B. Saka", "RW", 86, 86, 86, 55, 72,
       status="out")        # injured/suspended -> removed from sims
       status="doubtful"    # knock -> fewer minutes, reduced effectiveness
       form=1.12            # hot streak (0.80 cold ... 1.20 red hot)
       minutes=60           # expected minutes (rotation, late sub)
       pen_rank=1           # first-choice penalty taker
```

Losing a key player hurts twice: their quality leaves the zone average AND
an availability penalty kicks in because the zone is under-resourced.

Match conditions live in `CONTEXTS` in the same file — update the weather
forecast, crowd split, or rest days the same way (e.g. set `rain=0.7` if a
storm rolls in, or bump `wind_kmh` for an open-bowl coastal stadium).

## Adding teams

Copy any block in the data file. Positions: GK RB CB LB DM CM AM LW RW ST.
Ratings are 0–100 (analyst estimates in the demo data — deliberately
editable). Add a fixture tuple to `FIXTURES` if you want it in `--fixtures`.

## Extending with real data

The schema is the contract — swap hand-set ratings for data-driven ones:

- **FBref / StatsBomb / Understat**: map per-90 npxG, shot-creating actions,
  progressive carries, tackles+interceptions onto the six ratings.
- **Injury feeds**: scrape team news and flip `status` before each run.
- **Calibration**: backtest on past tournaments; tune `BASE_XG`,
  `ZONE_ELASTICITY`, `TEAM_SCORE_BASELINE`, and position multipliers so
  predicted probabilities match observed frequencies (reliability curves /
  Brier score).

Model outputs are estimates driven by the ratings you feed in — treat them
as a class-project forecasting tool, not betting advice.

## Project layout

```
main.py                         CLI entry point
soccer_sim/models.py            Player/Team classes, ratings, team scores
soccer_sim/matchup.py           zone battles -> expected goals
soccer_sim/context.py           stadium/weather/crowd/travel conditions
soccer_sim/simulator.py         vectorized 100k-sim Monte Carlo engine
soccer_sim/report.py            terminal report + JSON export
soccer_sim/data/worldcup2026.py editable rosters + venue conditions
```
