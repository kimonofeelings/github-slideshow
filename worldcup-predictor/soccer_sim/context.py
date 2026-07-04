"""
Match conditions engine: everything around the game, not just the players.

A MatchContext describes the stadium and circumstances of a specific match:
altitude, weather (heat/humidity/rain/wind), roof, pitch quality, crowd
size and allegiance, referee style, and each side's rest days and travel.
`context_effects()` converts all of it into one expected-goals multiplier
per team, with a factor-by-factor breakdown for the report.

Every factor is small, bounded, and directionally grounded in the
football-analytics literature (home advantage ~0.2-0.3 goals, altitude
and heat fatigue for unacclimated sides, wind disrupting service, etc.).
The player-matchup model stays the core signal; conditions tilt it.
"""

from dataclasses import dataclass


@dataclass
class MatchContext:
    venue: str = "Neutral venue"
    city: str = ""
    kickoff_local: str = ""
    # --- stadium -----------------------------------------------------------
    altitude_m: int = 0          # meters above sea level
    roof_closed: bool = False    # climate-controlled: weather neutralized
    pitch_quality: float = 1.00  # 0.85 chewed-up .. 1.00 perfect
    # --- weather (ignored when roof_closed) --------------------------------
    temp_c: float = 21.0
    humidity: float = 0.50       # 0..1
    rain: float = 0.0            # 0 dry .. 1 downpour
    wind_kmh: float = 8.0
    # --- crowd --------------------------------------------------------------
    crowd: int = 55_000
    home_support: float = 0.50   # share of crowd behind the first-listed team
    # --- referee -------------------------------------------------------------
    ref_strictness: float = 0.50  # 0 lets play flow .. 1 whistle-happy
    # --- per-side circumstances (first-listed team, second-listed team) ------
    rest_days: tuple = (4, 4)
    travel_km: tuple = (500, 500)          # since previous match
    altitude_adapted: tuple = (False, False)   # trains/plays at altitude
    heat_adapted: tuple = (False, False)       # used to hot-humid climates
    # --- provenance -----------------------------------------------------------
    source: str = ""             # e.g. "LIVE (fetched 2026-07-04 20:45 UTC)"


NEUTRAL = MatchContext()

# Per-factor caps keep any single condition from dominating the football.
TOTAL_CLAMP = (0.75, 1.30)


def _pair(label, a, b):
    return {"factor": label, "home": round(a, 3), "away": round(b, 3)}


def context_effects(ctx: MatchContext, team_a=None, team_b=None):
    """
    Returns (mult_home, mult_away, rows) where rows is a list of dicts
    {factor, home, away} — one per active condition — for reporting.
    Teams are only needed for the referee factor (physicality edge).
    """
    rows = []
    ma = mb = 1.0

    # 1) crowd support: bigger and more partisan = stronger push.
    #    A full 80k+ stadium entirely behind one side is worth ~+/-8% xG,
    #    consistent with observed home advantage of ~0.25 goals.
    intensity = min(ctx.crowd / 80_000, 1.0)
    edge = (ctx.home_support - 0.5) * 2.0          # -1 .. +1
    crowd_a = 1.0 + 0.08 * edge * intensity
    crowd_b = 1.0 - 0.08 * edge * intensity
    if abs(edge) > 0.02:
        rows.append(_pair("Crowd support", crowd_a, crowd_b))
    ma *= crowd_a
    mb *= crowd_b

    # 2) altitude: thin air tires unacclimated legs (up to -9%) but the
    #    ball also travels faster, a small boost for everyone (+4% max).
    if ctx.altitude_m >= 800:
        thin_air = 1.0 + min(ctx.altitude_m / 3000, 1.0) * 0.04
        fatigue = min((ctx.altitude_m - 800) / 2000, 1.0) * 0.09
        alt_a = thin_air * (1.0 if ctx.altitude_adapted[0] else 1.0 - fatigue)
        alt_b = thin_air * (1.0 if ctx.altitude_adapted[1] else 1.0 - fatigue)
        rows.append(_pair(f"Altitude {ctx.altitude_m}m", alt_a, alt_b))
        ma *= alt_a
        mb *= alt_b

    if not ctx.roof_closed:
        # 3) heat + humidity: slows tempo; acclimated teams cope better.
        stress = max(0.0, ctx.temp_c - 25.0) / 12.0 * (0.5 + 0.8 * ctx.humidity)
        stress = min(stress, 1.0)
        if stress > 0.03:
            heat_a = 1.0 - (0.03 if ctx.heat_adapted[0] else 0.08) * stress
            heat_b = 1.0 - (0.03 if ctx.heat_adapted[1] else 0.08) * stress
            rows.append(_pair(f"Heat {ctx.temp_c:.0f}C", heat_a, heat_b))
            ma *= heat_a
            mb *= heat_b

        # 4) rain: slick surface, keeper errors, deflections -> more goals.
        if ctx.rain > 0.05:
            wet = 1.0 + 0.05 * ctx.rain
            rows.append(_pair("Rain", wet, wet))
            ma *= wet
            mb *= wet

        # 5) wind: ruins crossing and long service for both sides.
        if ctx.wind_kmh > 15:
            windy = 1.0 - min((ctx.wind_kmh - 15) / 45, 1.0) * 0.07
            rows.append(_pair(f"Wind {ctx.wind_kmh:.0f}km/h", windy, windy))
            ma *= windy
            mb *= windy

    # 6) pitch: a poor surface suppresses chance creation for everyone.
    if ctx.pitch_quality < 0.995:
        pq = ctx.pitch_quality ** 0.4
        rows.append(_pair(f"Pitch {ctx.pitch_quality:.0%}", pq, pq))
        ma *= pq
        mb *= pq

    # 7) rest + travel fatigue since the previous match.
    def freshness(rest, km):
        f = 1.0
        if rest < 5:
            f *= max(0.90, 1.0 - 0.025 * (5 - rest))
        f *= 1.0 - min(max(km - 500, 0) / 10_000, 1.0) * 0.05
        return f
    fr_a = freshness(ctx.rest_days[0], ctx.travel_km[0])
    fr_b = freshness(ctx.rest_days[1], ctx.travel_km[1])
    if abs(fr_a - fr_b) > 0.005 or min(fr_a, fr_b) < 0.99:
        rows.append(_pair("Rest & travel", fr_a, fr_b))
    ma *= fr_a
    mb *= fr_b

    # 8) referee: a whistle-happy ref breaks up play, blunting the more
    #    physical side; a permissive ref lets them lean on the game.
    if team_a is not None and team_b is not None:
        def phys(team):
            core = team.outfield()
            w = sum(p.minutes_share for p in core) or 1.0
            return sum(p.physical * p.minutes_share for p in core) / w
        phys_edge = (phys(team_a) - phys(team_b)) / 100.0
        lean = (0.5 - ctx.ref_strictness) * 2.0   # +1 permissive .. -1 strict
        ref_a = 1.0 + 0.05 * lean * phys_edge
        ref_b = 1.0 - 0.05 * lean * phys_edge
        if abs(ref_a - 1.0) > 0.004:
            rows.append(_pair("Referee style", ref_a, ref_b))
        ma *= ref_a
        mb *= ref_b

    lo, hi = TOTAL_CLAMP
    return max(lo, min(hi, ma)), max(lo, min(hi, mb)), rows


def describe(ctx: MatchContext):
    """One-line weather/venue summary for the report header."""
    where = ctx.venue + (f", {ctx.city}" if ctx.city else "")
    if ctx.roof_closed:
        wx = "roof closed, climate controlled"
    else:
        bits = [f"{ctx.temp_c:.0f}C", f"{ctx.humidity:.0%} humidity",
                f"wind {ctx.wind_kmh:.0f} km/h"]
        if ctx.rain > 0.05:
            bits.append("rain" if ctx.rain < 0.6 else "heavy rain")
        wx = ", ".join(bits)
    extra = f" | altitude {ctx.altitude_m:,}m" if ctx.altitude_m >= 800 else ""
    ko = ""
    if ctx.kickoff_local:
        ko = f" | kickoff {ctx.kickoff_local}"
        if "UTC" not in ctx.kickoff_local:
            ko += " local"
    return f"{where} ({wx}{extra}{ko})"
