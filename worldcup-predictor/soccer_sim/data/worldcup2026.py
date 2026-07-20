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

# ----------------------------------------------------------------- PORTUGAL
TEAMS["POR"] = _team("POR", "Portugal", [
    Player("D. Costa",       "GK", 15, 55, 48, 84, 80),
    Player("J. Cancelo",     "RB", 55, 82, 82, 74, 72),
    Player("Ruben Dias",     "CB", 32, 70, 70, 89, 86),
    Player("G. Inacio",      "CB", 36, 72, 76, 83, 78),
    Player("N. Mendes",      "LB", 50, 74, 90, 80, 80),
    Player("J. Palhinha",    "DM", 38, 62, 66, 85, 88),
    Player("Vitinha",        "CM", 58, 88, 72, 74, 68),
    Player("Joao Neves",     "CM", 54, 84, 74, 78, 72),
    Player("B. Fernandes",   "AM", 82, 90, 70, 58, 72, pen_rank=1),
    Player("B. Silva",       "RW", 76, 88, 74, 62, 66),
    # Ronaldo at 41: still the box presence, legs long gone
    Player("C. Ronaldo",     "ST", 85, 68, 58, 30, 80, minutes=70, pen_rank=2),
    Player("G. Ramos",       "ST", 81, 66, 78, 38, 78, minutes=40),
    Player("R. Leao",        "LW", 84, 80, 92, 36, 78, form=1.05),
    Player("P. Neto",        "RW", 76, 74, 88, 42, 68, minutes=35),
    Player("A. Silva",       "CB", 30, 62, 62, 82, 82, minutes=25),
])

# -------------------------------------------------------------------- SPAIN
TEAMS["ESP"] = _team("ESP", "Spain", [
    Player("U. Simon",       "GK", 14, 62, 46, 84, 80),
    Player("P. Porro",       "RB", 52, 76, 80, 74, 72),
    Player("R. Le Normand",  "CB", 30, 66, 70, 84, 82),
    Player("P. Cubarsi",     "CB", 34, 80, 74, 86, 76, form=1.05),
    Player("M. Cucurella",   "LB", 46, 74, 78, 80, 74),
    # Rodri: the metronome, reigning Ballon d'Or midfielder
    Player("Rodri",          "DM", 55, 90, 62, 86, 84, form=1.05),
    Player("Pedri",          "CM", 62, 92, 72, 70, 64),
    Player("M. Zubimendi",   "CM", 48, 80, 66, 80, 76),
    Player("D. Olmo",        "AM", 78, 86, 74, 52, 66, minutes=70),
    # Yamal: the tournament's box-office attraction
    Player("L. Yamal",       "RW", 90, 94, 88, 40, 62, form=1.12, pen_rank=2),
    Player("N. Williams",    "LW", 83, 80, 93, 42, 72),
    Player("M. Oyarzabal",   "ST", 80, 78, 74, 50, 70, pen_rank=1),
    Player("A. Morata",      "ST", 78, 68, 72, 42, 78, minutes=35),
    Player("F. Ruiz",        "CM", 56, 84, 66, 74, 74, minutes=45),
    Player("A. Laporte",     "CB", 30, 70, 64, 83, 82, minutes=25),
])

# ------------------------------------------------------------- UNITED STATES
TEAMS["USA"] = _team("USA", "United States", [
    Player("M. Turner",      "GK", 12, 48, 44, 80, 78),
    Player("S. Dest",        "RB", 52, 76, 84, 70, 66),
    Player("C. Richards",    "CB", 32, 62, 76, 81, 82),
    Player("M. Zimmerman",   "CB", 26, 52, 62, 78, 86),
    Player("A. Robinson",    "LB", 46, 72, 84, 76, 76),
    Player("T. Adams",       "DM", 42, 68, 72, 82, 82),
    Player("W. McKennie",    "CM", 58, 72, 74, 74, 82),
    Player("Y. Musah",       "CM", 52, 74, 82, 72, 76),
    Player("G. Reyna",       "AM", 70, 84, 72, 50, 64, minutes=55),
    # Pulisic carrying home-nation expectations
    Player("C. Pulisic",     "LW", 84, 84, 86, 45, 68, form=1.10, pen_rank=1),
    Player("T. Weah",        "RW", 74, 70, 88, 50, 74),
    Player("F. Balogun",     "ST", 79, 66, 84, 36, 74, pen_rank=2),
    Player("R. Pepi",        "ST", 76, 60, 76, 34, 76, minutes=35),
    Player("J. Morris",      "RW", 62, 60, 80, 44, 74, minutes=25),
    Player("T. Ream",        "CB", 24, 66, 54, 78, 74, minutes=30),
])

# ------------------------------------------------------------------ BELGIUM
TEAMS["BEL"] = _team("BEL", "Belgium", [
    Player("T. Courtois",    "GK", 12, 58, 50, 89, 86),
    Player("T. Castagne",    "RB", 44, 66, 78, 76, 76),
    Player("Z. Debast",      "CB", 34, 72, 72, 80, 78),
    Player("W. Faes",        "CB", 28, 56, 74, 78, 82),
    Player("M. De Cuyper",   "LB", 46, 72, 78, 74, 72),
    Player("A. Onana",       "DM", 50, 74, 78, 82, 86),
    Player("Y. Tielemans",   "CM", 60, 84, 66, 74, 74),
    # De Bruyne at 35: slower, still sees passes nobody else does
    Player("K. De Bruyne",   "AM", 78, 93, 62, 52, 68, minutes=75, pen_rank=1),
    Player("J. Doku",        "RW", 78, 80, 94, 40, 70, form=1.05),
    Player("L. Trossard",    "LW", 76, 78, 78, 48, 66, minutes=60),
    Player("L. Openda",      "ST", 81, 70, 88, 36, 74, pen_rank=2),
    Player("R. Lukaku",      "ST", 82, 64, 72, 32, 90, minutes=45),
    Player("J. Bakayoko",    "RW", 72, 72, 88, 38, 68, minutes=30),
    Player("O. Vranckx",     "CM", 48, 66, 70, 72, 78, minutes=30),
])

# -------------------------------------------------------------- SWITZERLAND
TEAMS["SUI"] = _team("SUI", "Switzerland", [
    Player("G. Kobel",       "GK", 12, 54, 48, 85, 82),
    Player("S. Widmer",      "RB", 42, 66, 74, 74, 74),
    Player("M. Akanji",      "CB", 36, 74, 80, 86, 82),
    Player("N. Elvedi",      "CB", 28, 62, 74, 80, 78),
    Player("R. Rodriguez",   "LB", 40, 70, 64, 74, 72, minutes=70),
    Player("R. Freuler",     "DM", 46, 72, 68, 78, 76),
    # Xhaka at 33: still organizes everything
    Player("G. Xhaka",       "CM", 52, 84, 58, 78, 80),
    Player("F. Rieder",      "CM", 58, 80, 70, 66, 64),
    Player("A. Vargas",      "AM", 68, 76, 84, 48, 64),
    Player("D. Ndoye",       "RW", 72, 68, 88, 46, 74),
    Player("Z. Amdouni",     "LW", 70, 70, 80, 40, 68, minutes=60),
    Player("B. Embolo",      "ST", 76, 64, 82, 40, 84, pen_rank=1),
    Player("N. Okafor",      "ST", 72, 66, 86, 36, 72, minutes=35),
    Player("E. Comert",      "CB", 26, 56, 68, 76, 76, minutes=25),
])

# ----------------------------------------------------------------- COLOMBIA
TEAMS["COL"] = _team("COL", "Colombia", [
    Player("C. Vargas",      "GK", 12, 50, 46, 80, 80),
    Player("D. Munoz",       "RB", 54, 72, 84, 76, 78),
    Player("D. Sanchez",     "CB", 30, 60, 72, 82, 84),
    Player("J. Lucumi",      "CB", 28, 62, 78, 81, 78),
    Player("J. Mojica",      "LB", 42, 66, 78, 72, 72),
    Player("J. Lerma",       "DM", 46, 66, 70, 80, 86),
    Player("R. Rios",        "CM", 52, 76, 70, 76, 76),
    # James at 35: a half-space magician who no longer tracks back
    Player("J. Rodriguez",   "AM", 76, 92, 60, 40, 64, minutes=70, pen_rank=1),
    Player("J. Arias",       "RW", 72, 76, 80, 48, 66),
    # Luis Diaz: Colombia's difference-maker
    Player("L. Diaz",        "LW", 86, 82, 90, 44, 72, form=1.08, pen_rank=2),
    Player("J. Cordoba",     "ST", 78, 62, 82, 36, 84),
    Player("R. Borre",       "ST", 72, 66, 76, 44, 74, minutes=35),
    Player("J. Quintero",    "AM", 66, 84, 62, 38, 60, minutes=25),
    Player("Y. Mosquera",    "CB", 26, 54, 74, 76, 78, minutes=25),
])

# ------------------------------------------------------------------- FRANCE
TEAMS["FRA"] = _team("FRA", "France", [
    Player("M. Maignan",     "GK", 14, 62, 52, 87, 82),
    Player("J. Kounde",      "RB", 44, 74, 82, 84, 78),
    Player("W. Saliba",      "CB", 34, 72, 82, 89, 84),
    Player("I. Konate",      "CB", 30, 62, 80, 85, 86),
    Player("T. Hernandez",   "LB", 54, 74, 88, 76, 78),
    Player("A. Tchouameni",  "DM", 50, 76, 74, 84, 84),
    Player("E. Camavinga",   "CM", 54, 80, 80, 78, 76),
    Player("M. Olise",       "AM", 80, 88, 78, 46, 66, form=1.06),
    # Dembele: reigning Ballon d'Or, unplayable on his day
    Player("O. Dembele",     "RW", 88, 88, 90, 42, 66, form=1.10, pen_rank=2),
    # Mbappe: the tournament's most feared forward
    Player("K. Mbappe",      "ST", 95, 86, 96, 36, 78, form=1.10, pen_rank=1),
    Player("M. Thuram",      "ST", 82, 72, 84, 40, 86, minutes=45),
    Player("B. Barcola",     "LW", 80, 76, 92, 38, 68, minutes=55),
    Player("A. Griezmann",   "AM", 76, 86, 66, 60, 68, minutes=35),
    Player("D. Upamecano",   "CB", 30, 64, 78, 83, 84, minutes=30),
    Player("A. Rabiot",      "CM", 56, 74, 70, 76, 82, minutes=45),
])

# ------------------------------------------------------------------ MOROCCO
TEAMS["MAR"] = _team("MAR", "Morocco", [
    Player("Y. Bounou",      "GK", 12, 56, 48, 85, 80),
    # Hakimi: world-class, half of Morocco's attack comes down his side
    Player("A. Hakimi",      "RB", 68, 82, 92, 82, 78, form=1.08, pen_rank=2),
    Player("N. Aguerd",      "CB", 30, 62, 74, 84, 84),
    Player("A. Saiss",       "CB", 26, 58, 62, 78, 80, minutes=60),
    Player("N. Mazraoui",    "LB", 46, 74, 80, 80, 74),
    Player("S. Amrabat",     "DM", 42, 70, 72, 82, 86),
    Player("A. Ounahi",      "CM", 58, 82, 76, 68, 66),
    Player("I. Bennacer",    "CM", 52, 78, 68, 74, 72, minutes=55),
    # El Khannouss: Morocco's new creative hub
    Player("B. El Khannouss","AM", 72, 86, 78, 52, 64, form=1.06),
    Player("B. Diaz",        "RW", 78, 84, 82, 44, 62),
    Player("E. Ezzalzouli",  "LW", 70, 72, 88, 40, 66, minutes=60),
    Player("Y. En-Nesyri",   "ST", 78, 58, 78, 36, 86, pen_rank=1),
    Player("S. Rahimi",      "ST", 72, 64, 82, 38, 74, minutes=35),
    Player("O. El Hilali",   "RB", 40, 62, 78, 74, 70, minutes=20),
])

# ------------------------------------------------------- MATCH CONDITIONS
# Venue + circumstances for each real Round of 16 tie. Tuples are
# (first-listed team, second-listed team). Edit freely — e.g. bump `rain`
# if the forecast turns, or `crowd`/`home_support` after ticket news.
CONTEXTS = {
    # Indoor stadium in Atlanta: weather is a non-factor, but the crowd
    # skews heavily Argentine and Egypt had the longer trip in.
    ("ARG", "EGY"): MatchContext(
        venue="Mercedes-Benz Stadium", city="Atlanta", kickoff_local="18:00",
        roof_closed=True, crowd=71_000, home_support=0.64,
        ref_strictness=0.45,
        rest_days=(4, 4), travel_km=(1_300, 2_200),
    ),
    # New Jersey in July: can run hot and sticky. Brazil copes with
    # heat far better than Norway if it does.
    ("BRA", "NOR"): MatchContext(
        venue="MetLife Stadium", city="East Rutherford", kickoff_local="15:00",
        temp_c=29.0, humidity=0.65, wind_kmh=12, crowd=82_000,
        home_support=0.70, ref_strictness=0.50,
        heat_adapted=(True, False),
        rest_days=(4, 4), travel_km=(900, 1_900),
    ),
    # Estadio Azteca (now Banorte), 2,240m above sea level, ~87k almost
    # all in green. Mexico trains at altitude; England flew in from sea
    # level with one day less rest. The pitch has taken a beating.
    ("MEX", "ENG"): MatchContext(
        venue="Estadio Azteca", city="Mexico City", kickoff_local="19:00",
        altitude_m=2_240, temp_c=22.0, humidity=0.45, wind_kmh=9,
        pitch_quality=0.92, crowd=87_000, home_support=0.85,
        ref_strictness=0.55,
        altitude_adapted=(True, False),
        rest_days=(3, 4), travel_km=(0, 2_400),
    ),
    # Iberian derby indoors in Texas: enormous occasion, split crowd
    # with a slight Portuguese edge in Dallas-Fort Worth.
    ("POR", "ESP"): MatchContext(
        venue="AT&T Stadium", city="Arlington", kickoff_local="14:00",
        roof_closed=True, crowd=93_000, home_support=0.53,
        ref_strictness=0.55,
        rest_days=(4, 4), travel_km=(1_100, 1_400),
    ),
    # Co-hosts under the Lumen Field roar - one of the loudest crowds
    # in the tournament, heavily American.
    ("USA", "BEL"): MatchContext(
        venue="Lumen Field", city="Seattle", kickoff_local="17:00",
        temp_c=22.0, humidity=0.55, wind_kmh=10, crowd=69_000,
        home_support=0.85, ref_strictness=0.50,
        rest_days=(4, 4), travel_km=(1_100, 3_900),
    ),
    # BC Place, roof closed; big Colombian expat presence travels well.
    ("SUI", "COL"): MatchContext(
        venue="BC Place", city="Vancouver", kickoff_local="13:00",
        roof_closed=True, crowd=54_000, home_support=0.42,
        ref_strictness=0.50,
        rest_days=(4, 4), travel_km=(4_000, 4_200),
    ),
    # Foxborough in July: France heavy favorites but Morocco's fans
    # will outnumber and outsing them.
    ("FRA", "MAR"): MatchContext(
        venue="Gillette Stadium", city="Foxborough", kickoff_local="16:00",
        temp_c=27.0, humidity=0.60, wind_kmh=12, crowd=64_000,
        home_support=0.45, ref_strictness=0.50,
        rest_days=(5, 4), travel_km=(900, 1_300),
    ),
    # --- QUARTERFINALS -------------------------------------------------
    # Spain-Belgium under the SoFi canopy in LA.
    ("ESP", "BEL"): MatchContext(
        venue="SoFi Stadium", city="Inglewood", kickoff_local="12:00",
        roof_closed=True, crowd=70_000, home_support=0.55,
        ref_strictness=0.50,
        rest_days=(4, 3), travel_km=(2_200, 1_500),
    ),
    # Norway-England in Miami heat - Haaland vs Kane, round two of the
    # bracket's biggest slugfest, in the humidity neither is built for.
    ("NOR", "ENG"): MatchContext(
        venue="Hard Rock Stadium", city="Miami Gardens", kickoff_local="17:00",
        temp_c=31.0, humidity=0.72, wind_kmh=11, crowd=66_000,
        home_support=0.42, ref_strictness=0.50,
        rest_days=(6, 5), travel_km=(1_800, 1_900),
    ),
    # Argentina-Switzerland at Arrowhead - one of the loudest venues in
    # the tournament, heavily Albiceleste.
    ("ARG", "SUI"): MatchContext(
        venue="GEHA Field at Arrowhead Stadium", city="Kansas City",
        kickoff_local="20:00", temp_c=27.0, humidity=0.60, wind_kmh=12,
        crowd=73_000, home_support=0.70, ref_strictness=0.50,
        rest_days=(4, 4), travel_km=(1_100, 2_900),
    ),
    # --- SEMIFINALS ------------------------------------------------------
    # France-Spain indoors at AT&T: the tournament's two best squads.
    ("FRA", "ESP"): MatchContext(
        venue="AT&T Stadium", city="Arlington", kickoff_local="14:00",
        roof_closed=True, crowd=93_000, home_support=0.50,
        ref_strictness=0.50,
        rest_days=(5, 4), travel_km=(2_500, 2_000),
    ),
    # England-Argentina at Mercedes-Benz: a rematch of legends, huge
    # Argentine turnout expected.
    ("ENG", "ARG"): MatchContext(
        venue="Mercedes-Benz Stadium", city="Atlanta", kickoff_local="15:00",
        roof_closed=True, crowd=71_000, home_support=0.42,
        ref_strictness=0.55,
        rest_days=(4, 3), travel_km=(1_000, 1_100),
    ),
    # --- THIRD-PLACE GAME & FINAL ----------------------------------------
    # Bronze final in Miami heat: both squads coming off semifinal losses.
    ("FRA", "ENG"): MatchContext(
        venue="Hard Rock Stadium", city="Miami Gardens",
        kickoff_local="17:00", temp_c=32, humidity=0.75,
        crowd=65_000, home_support=0.50, ref_strictness=0.45,
        rest_days=(4, 3), travel_km=(1_800, 1_000),
    ),
    # The final at MetLife: Spain's press against Argentina's counters.
    ("ESP", "ARG"): MatchContext(
        venue="MetLife Stadium", city="East Rutherford",
        kickoff_local="15:00", temp_c=28, humidity=0.60,
        crowd=82_500, home_support=0.45, ref_strictness=0.55,
        rest_days=(5, 4), travel_km=(2_200, 1_200),
    ),
}

# Real fixtures covered by this data: R16 + QFs + SFs (played),
# then the third-place game (Jul 18) and the final (Jul 19)
FIXTURES = [("ARG", "EGY"), ("BRA", "NOR"), ("MEX", "ENG"),
            ("POR", "ESP"), ("USA", "BEL"), ("SUI", "COL"), ("FRA", "MAR"),
            ("ESP", "BEL"), ("NOR", "ENG"), ("ARG", "SUI"),
            ("FRA", "ESP"), ("ENG", "ARG"),
            ("FRA", "ENG"), ("ESP", "ARG")]


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
