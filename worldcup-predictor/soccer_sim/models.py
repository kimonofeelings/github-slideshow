"""
Core data models for the soccer match prediction engine.

Every player carries six base ratings on a 0-100 scale plus dynamic
modifiers (form, injury status, expected minutes). The matchup engine
converts these into zone-by-zone attacker-vs-defender comparisons.

Rating meanings
---------------
attack     : finishing, shot volume/quality, goal threat
creativity : passing, vision, dribbling, chance creation
pace       : speed + acceleration
defense    : tackling, positioning, marking (for GK: shot stopping)
physical   : strength, aerial ability, stamina
"""

from dataclasses import dataclass, field

# ---- player availability states -------------------------------------------
FIT = "fit"
DOUBTFUL = "doubtful"   # carrying a knock: reduced minutes + effectiveness
OUT = "out"             # injured / suspended: excluded from simulation

FITNESS_FACTOR = {FIT: 1.00, DOUBTFUL: 0.88, OUT: 0.00}
MINUTES_FACTOR = {FIT: 1.00, DOUBTFUL: 0.72, OUT: 0.00}

VALID_POSITIONS = {"GK", "RB", "CB", "LB", "DM", "CM", "AM", "LW", "RW", "ST"}

# --- team-score position weights --------------------------------------------
# How much each position's individual power counts toward the team's overall
# ATTACK and DEFENSE scores (0-100). A striker's finishing matters far more
# to the attack score than a center back's; the keeper anchors the defense.
ATTACK_SCORE_WEIGHTS = {
    "ST": 1.00, "LW": 0.90, "RW": 0.90, "AM": 0.85,
    "CM": 0.50, "DM": 0.25, "LB": 0.30, "RB": 0.30, "CB": 0.15, "GK": 0.00,
}
DEFENSE_SCORE_WEIGHTS = {
    "GK": 1.00, "CB": 1.00, "LB": 0.85, "RB": 0.85, "DM": 0.80,
    "CM": 0.50, "AM": 0.25, "LW": 0.20, "RW": 0.20, "ST": 0.15,
}


@dataclass
class Player:
    name: str
    position: str            # one of VALID_POSITIONS
    attack: int
    creativity: int
    pace: int
    defense: int
    physical: int
    form: float = 1.00       # 0.80 = ice cold ... 1.20 = red hot
    status: str = FIT        # fit / doubtful / out
    minutes: float = 90.0    # expected minutes when available
    pen_rank: int = 0        # 1 = first-choice penalty taker, 2 = backup

    def __post_init__(self):
        if self.position not in VALID_POSITIONS:
            raise ValueError(f"{self.name}: unknown position '{self.position}'")

    # -- derived quantities ---------------------------------------------
    @property
    def available(self) -> bool:
        return self.status != OUT

    @property
    def fitness(self) -> float:
        """Effectiveness multiplier from injury status."""
        return FITNESS_FACTOR[self.status]

    @property
    def minutes_share(self) -> float:
        """Fraction of the match this player is expected to be on the pitch."""
        eff = self.minutes * MINUTES_FACTOR[self.status]
        return min(eff, 96.0) / 96.0   # 96 ~ 90' + stoppage time

    def attacking_power(self) -> float:
        """Composite threat rating used in attacker-vs-defender matchups."""
        base = 0.40 * self.attack + 0.35 * self.creativity + 0.25 * self.pace
        return base * self.form * self.fitness

    def defending_power(self) -> float:
        """Composite stopping rating used in attacker-vs-defender matchups."""
        base = 0.55 * self.defense + 0.20 * self.pace + 0.25 * self.physical
        return base * self.form * self.fitness

    def midfield_power(self) -> float:
        """Composite rating for the midfield-control battle."""
        base = (0.35 * self.creativity + 0.30 * self.defense
                + 0.20 * self.physical + 0.15 * self.pace)
        return base * self.form * self.fitness


@dataclass
class Team:
    code: str                # short code, e.g. "ARG"
    name: str
    players: list = field(default_factory=list)

    # -- roster slices ----------------------------------------------------
    def squad(self, include_out: bool = False):
        return [p for p in self.players if include_out or p.available]

    def keeper(self) -> Player:
        gks = sorted((p for p in self.squad() if p.position == "GK"),
                     key=lambda p: p.defense * p.form * p.fitness,
                     reverse=True)
        if not gks:
            raise ValueError(f"{self.name} has no available goalkeeper")
        return gks[0]

    def outfield(self):
        return [p for p in self.squad() if p.position != "GK"]

    def by_positions(self, positions):
        return [p for p in self.squad() if p.position in positions]

    def team_form(self) -> float:
        """Average form of the likely core (minutes-weighted)."""
        core = self.outfield()
        w = sum(p.minutes_share for p in core) or 1.0
        return sum(p.form * p.minutes_share for p in core) / w

    # -- team-level quality scores ----------------------------------------
    def _score(self, weights, power_fn) -> float:
        num = den = 0.0
        for p in self.squad():
            w = weights.get(p.position, 0.0) * p.minutes_share
            if w > 0:
                num += w * power_fn(p)
                den += w
        return num / den if den else 45.0   # replacement-level fallback

    def attack_score(self) -> float:
        """
        Overall ATTACK score (0-100): minutes/fitness-weighted attacking
        power of the squad, position-weighted by goal-creation influence.
        Injuries and cold form pull it down automatically.
        """
        return self._score(ATTACK_SCORE_WEIGHTS, lambda p: p.attacking_power())

    def defense_score(self) -> float:
        """
        Overall DEFENSE score (0-100): minutes/fitness-weighted defending
        power including the goalkeeper (rated on shot stopping alone).
        """
        def power(p):
            if p.position == "GK":
                return p.defense * p.form * p.fitness
            return p.defending_power()
        return self._score(DEFENSE_SCORE_WEIGHTS, power)
