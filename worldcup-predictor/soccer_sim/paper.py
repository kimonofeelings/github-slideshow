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


def fetch_advance_prices():
    """{team_name_lower: yes_price} from Polymarket's quarterfinal
    markets, or {} when the API is unreachable."""
    data = get_json(GAMMA, ttl=600)
    prices = {}
    for e in data or []:
        if "Quarterfinal" not in (e.get("title") or ""):
            continue
        for m in e.get("markets", []):
            q = m.get("question") or ""
            if not q.startswith("Will ") or "reach the Quarterfinals" not in q:
                continue
            team = q[5:q.index(" reach")].strip().lower()
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
                px = json.loads(m.get("outcomePrices") or "[]")
                yes = float(px[outcomes.index("Yes")])
            except (ValueError, IndexError):
                continue
            prices[team] = yes
    return prices


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
        lines.append(
            f"\U0001F4B5 *${b['stake']:.0f} on {flag} {b['team']} to "
            f"advance* ({b['match']})\n"
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
