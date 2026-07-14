"""
Paper trading: the model bets FAKE money on its own predictions.

Markets come from Polymarket's public read-only API ("Will X reach the
Quarterfinals?" YES/NO prices), which map one-to-one onto the model's
advancement probabilities. When the model's probability diverges from
the market price by more than EDGE_MIN, it places a paper bet sized by
quarter-Kelly (capped at 5% of bankroll). Bets settle when the match is
graded. Everything - bankroll, open bets, settled record - lives in
soccer_sim/data/paper_trading.json and is committed, so the ledger is
auditable and survives restarts.

NO REAL MONEY moves anywhere. The point is measurement: after enough
settled bets the ROI says whether the model actually beats the market
(and until then, a big "edge" more likely means the model is missing
something the market knows - injuries, lineups, momentum).
"""

import json
import os
import time

from .live.http import get_json

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "paper_trading.json")

GAMMA = "https://gamma-api.polymarket.com/events?closed=false&tag_slug=world-cup"

START_BANKROLL = 1000.0
EDGE_MIN = 0.05          # model-vs-market gap required to bet
KELLY_FRACTION = 0.25    # quarter Kelly
MAX_STAKE_FRAC = 0.05    # never more than 5% of bankroll on one bet
MIN_STAKE = 5.0
PRICE_BOUNDS = (0.03, 0.97)   # skip near-settled markets


def _load():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"bankroll": START_BANKROLL, "start": START_BANKROLL,
                "open": [], "settled": []}


def _save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=1)


ROUNDS = ("Final", "Semifinals", "Quarterfinals")


def fetch_advance_prices(round_name=None):
    """{team_name_lower: yes_price} from Polymarket's 'Nation To Reach X'
    markets. When `round_name` is None, each team gets its price from the
    EARLIEST round it hasn't clinched yet - which is exactly the market
    that settles on the team's next match. {} when unreachable."""
    data = get_json(GAMMA, ttl=600)
    by_round = {r: {} for r in ROUNDS}
    for e in data or []:
        title = e.get("title") or ""
        rnd = next((r for r in ROUNDS if r in title), None)
        if rnd is None or "Reach" not in title.replace("reach", "Reach"):
            continue
        for m in e.get("markets", []):
            q = m.get("question") or ""
            if not q.startswith("Will ") or " reach " not in q.lower():
                continue
            team = q[5:q.lower().index(" reach ")].strip().lower()
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
                px = json.loads(m.get("outcomePrices") or "[]")
                yes = float(px[outcomes.index("Yes")])
            except (ValueError, IndexError):
                continue
            by_round[rnd][team] = yes
    if round_name:
        return by_round.get(round_name, {})
    # walk from latest round to earliest: keep the price from the first
    # round (in tournament order) the team hasn't already clinched
    merged = {}
    for rnd in ROUNDS:                      # Final -> SF -> QF
        for team, yes in by_round[rnd].items():
            if PRICE_BOUNDS[0] < yes < PRICE_BOUNDS[1]:
                merged[team] = yes          # later rounds overwritten below
    for rnd in ("Semifinals", "Quarterfinals"):
        for team, yes in by_round[rnd].items():
            if PRICE_BOUNDS[0] < yes < PRICE_BOUNDS[1]:
                merged[team] = yes
    return merged


WINNER_SLUG = "https://gamma-api.polymarket.com/events?slug=world-cup-winner"


def fetch_title_prices():
    """{team_name_lower: yes_price} from Polymarket's tournament-winner
    market ('Will X win the 2026 FIFA World Cup?'). Used once the
    per-round 'Nation To Reach X' markets have all settled. {} when
    unreachable."""
    data = get_json(WINNER_SLUG, ttl=600)
    prices = {}
    for e in data or []:
        for m in e.get("markets", []):
            q = m.get("question") or ""
            if not q.startswith("Will ") or " win the " not in q.lower():
                continue
            team = q[5:q.lower().index(" win the ")].strip().lower()
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
                px = json.loads(m.get("outcomePrices") or "[]")
                yes = float(px[outcomes.index("Yes")])
            except (ValueError, IndexError, TypeError):
                continue
            if PRICE_BOUNDS[0] < yes < PRICE_BOUNDS[1]:
                prices[team] = yes
    return prices


def consider_title_bets():
    """One paper bet on the tournament-winner market: model title odds
    (exact bracket math) vs Polymarket's winner prices. At most one
    TITLE bet open at a time. Returns (note_lines, newly_placed)."""
    from .tournament import title_odds
    from .data.worldcup2026 import TEAMS

    state = _load()
    if any(b["match"] == "TITLE" for b in state["open"]):
        return [], []
    prices = fetch_title_prices()
    if not prices:
        return ["paper TITLE: winner-market prices unavailable"], []
    candidates = []
    for code, p_model in title_odds().items():
        team = TEAMS.get(code)
        q = prices.get(team.name.lower()) if team else None
        if q is None:
            continue
        edge = p_model - q
        if edge >= EDGE_MIN:
            candidates.append((edge, code, p_model, q))
    if not candidates:
        return [f"paper TITLE: no edge >= {EDGE_MIN:.0%} - pass"], []
    edge, code, p_model, q = max(candidates)
    stake = round(_kelly_stake(state["bankroll"], p_model, q), 2)
    if stake < MIN_STAKE:
        return [f"paper TITLE: edge on {code} but stake too small - pass"], []
    bet = {"match": "TITLE", "team": code, "price": q,
           "model_p": round(p_model, 3), "edge": round(edge, 3),
           "stake": stake, "placed": time.strftime("%Y-%m-%d %H:%MZ",
                                                   time.gmtime())}
    state["open"].append(bet)
    state["bankroll"] = round(state["bankroll"] - stake, 2)
    _save(state)
    return [f"paper: ${stake:.0f} on {code} to WIN THE CUP @ "
            f"{q:.0%} market vs {p_model:.0%} model (edge +{edge:.0%})"], [bet]


def settle_title(champion_code):
    """Resolve open TITLE bets once the champion is known."""
    state = _load()
    notes = []
    still_open = []
    for bet in state["open"]:
        if bet["match"] != "TITLE":
            still_open.append(bet)
            continue
        won = bet["team"] == champion_code
        payout = round(bet["stake"] / bet["price"], 2) if won else 0.0
        pnl = round(payout - bet["stake"], 2)
        state["bankroll"] = round(state["bankroll"] + payout, 2)
        bet.update(won=won, pnl=pnl, advanced=champion_code)
        state["settled"].append(bet)
        notes.append(f"paper TITLE: {bet['team']} @ {bet['price']:.0%} "
                     f"{'WON +$%.0f' % pnl if won else 'LOST -$%.0f' % bet['stake']}"
                     f" | bankroll ${state['bankroll']:.0f}")
    state["open"] = still_open
    _save(state)
    return notes


def _kelly_stake(bankroll, p_win, price):
    """Quarter-Kelly stake for buying a binary share at `price` that
    pays 1.0 when it wins."""
    b = (1.0 - price) / price          # net odds per unit staked
    f = (p_win * (b + 1) - 1) / b
    f = max(0.0, f) * KELLY_FRACTION
    return min(f, MAX_STAKE_FRAC) * bankroll


def consider_bets(results):
    """Given fresh SimulationResults, place at most one paper bet per
    match on the biggest model-vs-market edge.
    Returns (note_lines, newly_placed_bets)."""
    prices = fetch_advance_prices()
    if not prices:
        return ["paper: market prices unavailable - no bets placed"], []
    state = _load()
    notes = []
    placed = []
    open_matches = {b["match"] for b in state["open"]}
    settled_matches = {b["match"] for b in state["settled"]}

    for res in results:
        fc = res.forecast
        A, B = fc.home.team, fc.away.team
        match = f"{A.code}-{B.code}"
        if match in open_matches or match in settled_matches:
            continue
        candidates = []
        for team, p_model in ((A, res.p_home_advance),
                              (B, res.p_away_advance)):
            q = prices.get(team.name.lower())
            if q is None or not (PRICE_BOUNDS[0] < q < PRICE_BOUNDS[1]):
                continue
            edge = p_model - q
            if edge >= EDGE_MIN:
                candidates.append((edge, team.code, p_model, q))
        if not candidates:
            notes.append(f"paper {match}: no edge >= {EDGE_MIN:.0%} - pass")
            continue
        edge, code, p_model, q = max(candidates)
        stake = round(_kelly_stake(state["bankroll"], p_model, q), 2)
        if stake < MIN_STAKE:
            notes.append(f"paper {match}: edge on {code} but stake too "
                         f"small - pass")
            continue
        bet = {
            "match": match, "team": code, "price": q,
            "model_p": round(p_model, 3), "edge": round(edge, 3),
            "stake": stake, "placed": time.strftime("%Y-%m-%d %H:%MZ",
                                                    time.gmtime())}
        state["open"].append(bet)
        placed.append(bet)
        state["bankroll"] = round(state["bankroll"] - stake, 2)
        notes.append(f"paper: ${stake:.0f} on {code} to advance @ "
                     f"{q:.0%} market vs {p_model:.0%} model "
                     f"(edge +{edge:.0%})")
    _save(state)
    return notes, placed


def build_bet_slip(bets, title="PAPER BET SLIP"):
    """WhatsApp-formatted slip for a list of bets (fake money)."""
    from .notify import FLAGS
    state = _load()
    lines = [f"\U0001F39F *{title}*"]
    for b in bets:
        flag = FLAGS.get(b["team"], "")
        payout = b["stake"] / b["price"]
        what = ("WIN THE CUP* \U0001F3C6" if b["match"] == "TITLE"
                else f"advance* ({b['match']})")
        lines.append(
            f"\U0001F4B5 *${b['stake']:.0f} on {flag} {b['team']} to "
            f"{what}\n"
            f"   @ {b['price']:.0%} market vs *{b['model_p']:.0%} model* "
            f"(edge +{b['edge']:.0%})\n"
            f"   pays ${payout:.0f} if it hits")
    lines.append(f"\U0001F3E6 Bankroll: ${state['bankroll']:.0f} cash + "
                 f"${sum(b['stake'] for b in state['open']):.0f} at risk")
    lines.append("_Fake money - measuring the model's edge_")
    return "\n".join(lines)


def settle(home_code, away_code, advanced_code):
    """Resolve open bets on this match. Returns note lines."""
    state = _load()
    match = f"{home_code}-{away_code}"
    notes = []
    still_open = []
    for bet in state["open"]:
        if bet["match"] != match:
            still_open.append(bet)
            continue
        won = bet["team"] == advanced_code
        payout = round(bet["stake"] / bet["price"], 2) if won else 0.0
        pnl = round(payout - bet["stake"], 2)
        state["bankroll"] = round(state["bankroll"] + payout, 2)
        bet.update(won=won, pnl=pnl, advanced=advanced_code)
        state["settled"].append(bet)
        notes.append(f"paper: {bet['team']} @ {bet['price']:.0%} "
                     f"{'WON +$%.0f' % pnl if won else 'LOST -$%.0f' % bet['stake']}"
                     f" | bankroll ${state['bankroll']:.0f}")
    state["open"] = still_open
    _save(state)
    return notes


def summary_line():
    state = _load()
    equity = state["bankroll"] + sum(b["stake"] for b in state["open"])
    roi = (equity - state["start"]) / state["start"]
    wins = sum(1 for b in state["settled"] if b.get("won"))
    return (f"Paper bets: ${equity:,.0f} ({roi:+.1%}) | "
            f"{wins}-{len(state['settled']) - wins} record | "
            f"{len(state['open'])} open")
