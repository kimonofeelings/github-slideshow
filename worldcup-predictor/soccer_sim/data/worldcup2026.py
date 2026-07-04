"""
World Cup 2026 - Round of 16 demo rosters (6 teams, 3 real fixtures):

    ARG vs EGY   |   BRA vs NOR   |   MEX vs ENG

Ratings are ANALYST ESTIMATES on a 0-100 scale, meant as an editable
starting point - the whole point of the schema is that you replace or
tune these with real data (FBref, Understat, WhoScored exports, etc.).

To reflect team news before a match, edit in place:
    status="out"        -> excluded from the simulation entirely
    status="doubtful"   -> reduced minutes and effectiveness
    form=1.10           -> hot streak (0.80 cold ... 1.20 red hot)
    minutes=60          -> expected minutes (rotation / late sub)

Player(name, position, attack, creativity, pace, defense, physical, ...)
"""

from ..models import Player, Team
from ..context import MatchContext


def _team(code, name, players):
    return Team(code=code, name=name, players=players)


TEAMS = {}

# ---------------------------------------------------------------- ARGENTINA
TEAMS["ARG"] = _team("ARG", "Argentina", [
    Player("E. Martinez",    "GK", 20, 55, 45, 87, 82),
    Player("N. Molina",      "RB", 45, 70, 82, 78, 74),
    Player("C. Romero",      "CB", 35, 60, 74, 88, 86),
    Player("L. Martinez",    "CB", 30, 68, 76, 86, 82),
    Player("N. Tagliafico",  "LB", 40, 68, 74, 80, 76),
    Player("R. De Paul",     "CM", 55, 84, 74, 76, 80),
    Player("E. Fernandez",   "CM", 62, 86, 72, 78, 79),
    Player("A. Mac Allister","CM", 66, 85, 70, 77, 76),
    # Messi: 7 goals so far this tournament -> hot form, pens
    Player("L. Messi",       "AM", 93, 96, 72, 30, 62, form=1.15, minutes=85, pen_rank=1),
    Player("J. Alvarez",     "ST", 88, 78, 84, 55, 76, form=1.05, pen_rank=2),
    Player("T. Almada",      "LW", 75, 82, 84, 48, 64, minutes=60),
    Player("N. Paz",         "AM", 76, 85, 76, 50, 68, minutes=55, form=1.05),
    Player("N. Gonzalez",    "LW", 72, 74, 82, 60, 74, minutes=45),
    Player("L. Martinez L.", "ST", 87, 70, 78, 45, 80, minutes=35),
    Player("A. Garnacho",    "RW", 78, 76, 88, 40, 70, minutes=30),
    Player("N. Otamendi",    "CB", 25, 55, 60, 82, 84, minutes=20),
])

# -------------------------------------------------------------------- EGYPT
TEAMS["EGY"] = _team("EGY", "Egypt", [
    Player("M. El Shenawy",  "GK", 15, 45, 40, 78, 78),
    Player("M. Hany",        "RB", 40, 62, 74, 74, 72),
    Player("M. Abdelmonem",  "CB", 30, 58, 70, 80, 80),
    Player("R. Rabia",       "CB", 28, 55, 64, 76, 78),
    Player("A. Fatouh",      "LB", 38, 62, 76, 72, 70),
    Player("M. Attia",       "DM", 40, 62, 66, 78, 82),
    Player("E. Ashour",      "CM", 60, 76, 72, 70, 76),
    Player("H. Fathy",       "CM", 44, 60, 64, 72, 76, minutes=45),
    # Salah: Egypt's engine, first R16 in their history
    Player("M. Salah",       "RW", 90, 88, 86, 35, 76, form=1.10, pen_rank=1),
    Player("O. Marmoush",    "ST", 84, 80, 86, 40, 74, form=1.05, pen_rank=2),
    Player("Zizo",           "RW", 66, 76, 76, 58, 70, minutes=55),
    Player("Trezeguet",      "LW", 70, 72, 80, 45, 72, minutes=60),
    Player("M. Mohamed",     "ST", 74, 58, 72, 38, 84, minutes=50),
    Player("M. Elneny",      "CM", 45, 68, 58, 70, 70, minutes=25),
    Player("O. Fayed",       "CB", 22, 48, 66, 72, 76, minutes=15),
])

# ------------------------------------------------------------------- BRAZIL
TEAMS["BRA"] = _team("BRA", "Brazil", [
    Player("Alisson",        "GK", 15, 60, 50, 88, 84),
    Player("Vanderson",      "RB", 50, 74, 84, 74, 74),
    Player("Marquinhos",     "CB", 35, 72, 74, 87, 82),
    Player("Gabriel M.",     "CB", 40, 62, 70, 87, 88),
    Player("Wendell",        "LB", 42, 70, 78, 76, 74),
    Player("Casemiro",       "DM", 50, 72, 58, 82, 86, minutes=70),
    Player("Bruno Guimaraes","CM", 58, 85, 70, 78, 82),
    Player("Andrey Santos",  "CM", 62, 76, 74, 76, 80, minutes=60),
    Player("Raphinha",       "RW", 87, 86, 84, 52, 72, form=1.10, pen_rank=1),
    Player("Vinicius Jr",    "LW", 89, 88, 92, 40, 72, form=1.05),
    # Martinelli scored the winner vs Japan in the Round of 32
    Player("G. Martinelli",  "LW", 80, 74, 90, 45, 72, minutes=50, form=1.10),
    Player("Joao Pedro",     "ST", 81, 76, 78, 42, 76, minutes=70),
    Player("M. Cunha",       "ST", 80, 78, 76, 48, 74, minutes=40),
    Player("Estevao",        "RW", 80, 84, 86, 38, 60, minutes=45, form=1.08),
    Player("E. Militao",     "CB", 40, 64, 78, 84, 82, minutes=25),
])

# ------------------------------------------------------------------- NORWAY
TEAMS["NOR"] = _team("NOR", "Norway", [
    Player("O. Nyland",      "GK", 12, 42, 40, 76, 80),
    Player("J. Ryerson",     "RB", 45, 66, 78, 76, 78),
    Player("K. Ajer",        "CB", 35, 60, 72, 80, 84),
    Player("L. Ostigard",    "CB", 30, 54, 68, 78, 84),
    Player("D. Wolfe",       "LB", 42, 64, 80, 74, 76),
    Player("P. Berg",        "DM", 45, 74, 60, 76, 74),
    Player("S. Berge",       "CM", 50, 72, 68, 78, 84),
    Player("F. Aursnes",     "CM", 48, 72, 70, 74, 74, minutes=45),
    Player("M. Odegaard",    "AM", 78, 93, 70, 55, 66, form=1.05, pen_rank=2),
    # Haaland: the entire game plan runs through him
    Player("E. Haaland",     "ST", 96, 62, 90, 30, 92, form=1.12, pen_rank=1),
    Player("A. Sorloth",     "ST", 82, 58, 72, 35, 90, minutes=35),
    Player("A. Nusa",        "LW", 78, 82, 90, 40, 68, form=1.05),
    Player("O. Bobb",        "RW", 74, 82, 84, 42, 62, minutes=65),
    Player("M. Thorsby",     "CM", 48, 58, 66, 74, 86, minutes=30),
])

# ------------------------------------------------------------------- MEXICO
TEAMS["MEX"] = _team("MEX", "Mexico", [
    Player("L. Malagon",     "GK", 14, 48, 44, 78, 76),
    Player("J. Sanchez",     "RB", 40, 60, 78, 72, 74),
    Player("C. Montes",      "CB", 35, 58, 68, 80, 84),
    Player("J. Vasquez",     "CB", 32, 60, 70, 80, 80),
    Player("J. Gallardo",    "LB", 40, 64, 78, 72, 72),
    Player("E. Alvarez",     "DM", 45, 70, 64, 84, 86),
    Player("L. Chavez",      "CM", 60, 74, 66, 72, 74),
    Player("L. Romo",        "CM", 50, 68, 64, 74, 76, minutes=45),
    # Mora: 17-year-old breakout star of the co-hosts' run
    Player("G. Mora",        "AM", 72, 84, 78, 48, 60, form=1.10, minutes=75),
    Player("H. Lozano",      "RW", 76, 74, 86, 48, 70),
    Player("S. Gimenez",     "ST", 82, 66, 76, 38, 78, form=1.05, pen_rank=1),
    Player("R. Jimenez",     "ST", 76, 70, 64, 40, 80, minutes=30, pen_rank=2),
    Player("J. Quinones",    "LW", 74, 68, 82, 42, 76, minutes=55),
    Player("A. Vega",        "LW", 72, 72, 80, 44, 70, minutes=45),
    Player("R. Huescas",     "RB", 42, 62, 82, 70, 70, minutes=20),
])

# ------------------------------------------------------------------ ENGLAND
TEAMS["ENG"] = _team("ENG", "England", [
    Player("J. Pickford",    "GK", 15, 58, 46, 84, 78),
    Player("R. James",       "RB", 52, 80, 80, 80, 80),
    Player("J. Stones",      "CB", 42, 78, 74, 85, 80),
    Player("M. Guehi",       "CB", 35, 66, 74, 85, 80),
    Player("M. Lewis-Skelly","LB", 45, 76, 78, 78, 74),
    Player("D. Rice",        "DM", 55, 78, 76, 86, 86),
    Player("A. Wharton",     "CM", 48, 82, 64, 74, 70, minutes=55),
    Player("J. Bellingham",  "AM", 82, 86, 78, 70, 84, form=1.05),
    Player("C. Palmer",      "AM", 85, 89, 76, 45, 68, form=1.05, pen_rank=2, minutes=75),
    Player("B. Saka",        "RW", 86, 86, 86, 55, 72, form=1.08),
    # Kane: brace in the closing minutes vs DR Congo
    Player("H. Kane",        "ST", 93, 84, 62, 40, 86, form=1.12, pen_rank=1),
    Player("A. Gordon",      "LW", 78, 76, 90, 45, 70, minutes=60),
    Player("M. Rashford",    "LW", 79, 76, 86, 40, 78, minutes=35),
    Player("P. Foden",       "AM", 80, 85, 76, 45, 64, minutes=30),
    Player("O. Watkins",     "ST", 79, 64, 84, 38, 76, minutes=20),
    Player("E. Konsa",       "CB", 34, 62, 76, 82, 78, minutes=20),
])

# ------------------------------------------------------- MATCH CONDITIONS
# Venue + circumstances for each real Round of 16 tie. Tuples are
# (first-listed team, second-listed team). Edit freely — e.g. bump `rain`
# if the forecast turns, or `crowd`/`home_support` after ticket news.
CONTEXTS = {
    # Indoor stadium in Texas: weather is a non-factor, but the crowd
    # skews heavily Argentine and Egypt had the longer trip in.
    ("ARG", "EGY"): MatchContext(
        venue="AT&T Stadium", city="Arlington", kickoff_local="18:00",
        roof_closed=True, crowd=80_000, home_support=0.64,
        ref_strictness=0.45,
        rest_days=(4, 4), travel_km=(1_300, 2_200),
    ),
    # Miami in summer: brutal heat and humidity. Brazil lives in this
    # climate; Norway very much does not.
    ("BRA", "NOR"): MatchContext(
        venue="Hard Rock Stadium", city="Miami", kickoff_local="15:00",
        temp_c=32.0, humidity=0.78, wind_kmh=12, crowd=65_000,
        home_support=0.72, ref_strictness=0.50,
        heat_adapted=(True, False),
        rest_days=(4, 4), travel_km=(900, 1_900),
    ),
    # Estadio Azteca, 2,240m above sea level, ~87k almost all in green.
    # Mexico trains at altitude; England flew in from sea level with one
    # day less rest. The pitch has taken a beating all tournament.
    ("MEX", "ENG"): MatchContext(
        venue="Estadio Azteca", city="Mexico City", kickoff_local="19:00",
        altitude_m=2_240, temp_c=22.0, humidity=0.45, wind_kmh=9,
        pitch_quality=0.92, crowd=87_000, home_support=0.85,
        ref_strictness=0.55,
        altitude_adapted=(True, False),
        rest_days=(3, 4), travel_km=(0, 2_400),
    ),
}

# Real Round of 16 fixtures covered by this demo data
FIXTURES = [("ARG", "EGY"), ("BRA", "NOR"), ("MEX", "ENG")]


def get_team(code):
    code = code.upper()
    if code not in TEAMS:
        raise KeyError(f"Unknown team '{code}'. Available: {', '.join(TEAMS)}")
    return TEAMS[code]


def get_context(home, away):
    """Known real-fixture conditions for this pairing, else None (neutral).
    Checks the reversed pairing too, swapping the per-side tuples."""
    home, away = home.upper(), away.upper()
    ctx = CONTEXTS.get((home, away))
    if ctx:
        return ctx
    rev = CONTEXTS.get((away, home))
    if rev:
        from dataclasses import replace
        return replace(
            rev,
            home_support=1.0 - rev.home_support,
            rest_days=rev.rest_days[::-1],
            travel_km=rev.travel_km[::-1],
            altitude_adapted=rev.altitude_adapted[::-1],
            heat_adapted=rev.heat_adapted[::-1],
        )
    return None
