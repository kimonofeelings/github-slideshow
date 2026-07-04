"""
Matchup engine: converts player-vs-defender battles into expected goals.

The pitch is split into three attacking zones (left / center / right).
Team A's left-side attackers are matched against Team B's right-side
defenders, center vs center, right vs left. Each zone produces a
multiplier from the ratio of attacking power to defending power; those
multipliers, plus the midfield-control battle and the opposing keeper,
scale a baseline expected-goals figure for the match.

Output: MatchForecast with lambda (expected goals) for each side and a
full per-zone breakdown so you can inspect *why* the model favors a team.
"""

from dataclasses import dataclass, field
from .models import Team
from .context import MatchContext, NEUTRAL, context_effects

# Baseline expected goals per team in an evenly-matched knockout game.
# (World Cup knockout matches average ~2.4-2.6 total goals in 90'.)
BASE_XG = 1.28

# How strongly a talent gap in a zone converts to more/fewer chances.
ZONE_ELASTICITY = 1.6

# Relative importance of each attacking zone to overall goal creation.
ZONE_BLEND = {"L": 0.27, "C": 0.46, "R": 0.27}

# --- positional contribution weights ----------------------------------------
# How much each position contributes to ATTACKING a given zone.
# Example: in the left zone, the LW is the primary threat, with the
# overlapping LB, the AM drifting wide, and the ST making near-post runs.
ATT_WEIGHTS = {
    "L": {"LW": 1.00, "LB": 0.35, "AM": 0.35, "ST": 0.30, "CM": 0.15, "RW": 0.10},
    "C": {"ST": 1.00, "AM": 0.80, "CM": 0.35, "LW": 0.30, "RW": 0.30, "DM": 0.10},
    "R": {"RW": 1.00, "RB": 0.35, "AM": 0.35, "ST": 0.30, "CM": 0.15, "LW": 0.10},
}

# How much each position contributes to DEFENDING a given attack zone.
# Note the mirroring: the defending RB meets the attacking LW.
DEF_WEIGHTS = {
    "L": {"RB": 1.00, "CB": 0.45, "DM": 0.35, "CM": 0.20, "RW": 0.15},
    "C": {"CB": 1.00, "DM": 0.70, "CM": 0.30, "RB": 0.15, "LB": 0.15},
    "R": {"LB": 1.00, "CB": 0.45, "DM": 0.35, "CM": 0.20, "LW": 0.15},
}

MID_POSITIONS = ("DM", "CM", "AM")
AVG_GK_RATING = 78.0   # tournament-average keeper benchmark

# --- team-level attack/defense scores ----------------------------------------
# Zone ratios above capture the RELATIVE matchup; these capture ABSOLUTE
# quality: an elite attack creates more chances against anyone, an elite
# defense concedes fewer against anyone. Each side's lambda is scaled by its
# attack score and the opponent's defense score, both measured against a
# tournament-average baseline.
TEAM_SCORE_BASELINE = 76.5
ATT_SCORE_ELASTICITY = 0.65
DEF_SCORE_ELASTICITY = 0.65


# --- helpers -----------------------------------------------------------------
def _weighted_group_power(players, weights, power_fn):
    """
    Minutes/fitness-weighted average power of a positional group, plus an
    availability penalty: if listed contributors are OUT or playing reduced
    minutes, the zone is weaker than its nominal full-strength version.

    Returns (effective_power, availability_factor, contributors)
    """
    num = den = 0.0
    nominal = 0.0
    contributors = []
    for p in players:
        w = weights.get(p.position, 0.0)
        if w == 0.0:
            continue
        nominal += w * min(p.minutes, 96.0) / 96.0
        eff_w = w * p.minutes_share            # 0 when OUT
        if eff_w > 0:
            num += eff_w * power_fn(p)
            den += eff_w
            contributors.append((p, eff_w))
    if den == 0.0:                              # nobody left in this zone
        return 45.0, 0.75, []                   # replacement-level fallback
    availability = 1.0
    if nominal > 0:
        availability = max(0.75, min(1.0, den / nominal))
    return num / den, availability, contributors


def _zone_multiplier(att_power, def_power):
    ratio = att_power / max(def_power, 1e-6)
    mult = ratio ** ZONE_ELASTICITY
    return max(0.55, min(1.85, mult))


# --- results containers --------------------------------------------------------
@dataclass
class ZoneBattle:
    zone: str
    att_power: float
    def_power: float
    multiplier: float
    key_attackers: list = field(default_factory=list)   # (name, weight)
    key_defenders: list = field(default_factory=list)


@dataclass
class TeamForecast:
    team: Team
    lam: float                       # expected goals for this team
    zones: dict = field(default_factory=dict)   # zone -> ZoneBattle
    midfield_mult: float = 1.0
    gk_mult: float = 1.0
    form_mult: float = 1.0
    attack_score: float = 0.0        # this team's overall attack (0-100)
    defense_score: float = 0.0       # this team's overall defense (0-100)
    att_score_mult: float = 1.0      # own attack score vs baseline
    def_score_mult: float = 1.0      # opponent defense score suppression
    ctx_mult: float = 1.0            # match-conditions multiplier


@dataclass
class MatchForecast:
    home: TeamForecast
    away: TeamForecast
    context: MatchContext = None
    context_rows: list = field(default_factory=list)  # factor breakdown


# --- main entry -----------------------------------------------------------------
def forecast_match(team_a: Team, team_b: Team,
                   context: MatchContext = None) -> MatchForecast:
    ctx = context or NEUTRAL
    ctx_a, ctx_b, rows = context_effects(ctx, team_a, team_b)
    fa = _forecast_side(attacking=team_a, defending=team_b, ctx_mult=ctx_a)
    fb = _forecast_side(attacking=team_b, defending=team_a, ctx_mult=ctx_b)
    return MatchForecast(home=fa, away=fb, context=context, context_rows=rows)


def _forecast_side(attacking: Team, defending: Team,
                   ctx_mult: float = 1.0) -> TeamForecast:
    att_players = attacking.squad()
    def_players = defending.squad()

    # 1) zone-by-zone player battles
    zones = {}
    blended = 0.0
    for zone, blend_w in ZONE_BLEND.items():
        ap, a_avail, a_who = _weighted_group_power(
            att_players, ATT_WEIGHTS[zone], lambda p: p.attacking_power())
        dp, d_avail, d_who = _weighted_group_power(
            def_players, DEF_WEIGHTS[zone], lambda p: p.defending_power())
        mult = _zone_multiplier(ap * a_avail, dp * d_avail)
        a_who.sort(key=lambda t: t[1] * t[0].attacking_power(), reverse=True)
        d_who.sort(key=lambda t: t[1] * t[0].defending_power(), reverse=True)
        zones[zone] = ZoneBattle(
            zone=zone, att_power=ap * a_avail, def_power=dp * d_avail,
            multiplier=mult,
            key_attackers=[(p.name, round(w, 2)) for p, w in a_who[:3]],
            key_defenders=[(p.name, round(w, 2)) for p, w in d_who[:3]],
        )
        blended += blend_w * mult

    # 2) midfield control battle (possession / territory)
    a_mid, _, _ = _weighted_group_power(
        attacking.by_positions(MID_POSITIONS), {p: 1.0 for p in MID_POSITIONS},
        lambda p: p.midfield_power())
    b_mid, _, _ = _weighted_group_power(
        defending.by_positions(MID_POSITIONS), {p: 1.0 for p in MID_POSITIONS},
        lambda p: p.midfield_power())
    mid_mult = max(0.85, min(1.18, (a_mid / max(b_mid, 1e-6)) ** 0.5))

    # 3) opposing goalkeeper suppresses (or leaks) finishing
    gk = defending.keeper()
    gk_eff = gk.defense * gk.form * gk.fitness
    gk_mult = max(0.90, min(1.10, (AVG_GK_RATING / max(gk_eff, 1e-6)) ** 0.9))

    # 4) team-wide form
    form_mult = max(0.90, min(1.12, attacking.team_form()))

    # 5) absolute quality: team attack score vs opponent defense score
    att_score = attacking.attack_score()
    opp_def_score = defending.defense_score()
    att_mult = max(0.70, min(1.40,
        (att_score / TEAM_SCORE_BASELINE) ** ATT_SCORE_ELASTICITY))
    def_mult = max(0.70, min(1.40,
        (TEAM_SCORE_BASELINE / max(opp_def_score, 1e-6)) ** DEF_SCORE_ELASTICITY))

    lam = (BASE_XG * blended * mid_mult * gk_mult * form_mult
           * att_mult * def_mult * ctx_mult)
    lam = max(0.25, min(4.0, lam))

    return TeamForecast(team=attacking, lam=lam, zones=zones,
                        midfield_mult=mid_mult, gk_mult=gk_mult,
                        form_mult=form_mult,
                        attack_score=att_score,
                        defense_score=attacking.defense_score(),
                        att_score_mult=att_mult, def_score_mult=def_mult,
                        ctx_mult=ctx_mult)
