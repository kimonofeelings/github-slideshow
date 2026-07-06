"""
Two-way texting: read the user's WhatsApp replies and answer commands.

The Twilio sandbox has no webhook here, so we poll the Messages API
for inbound texts instead. Any run can call `process()` - the daily
routine, every live-match poll (so replies are fast during games), and
an hourly sweep. Processed-message state lives in the cache dir; on
first run it fast-forwards past history so old replies are not
re-answered.

Commands (case-insensitive, first word wins):
  MENU / HELP      what you can text
  ODDS / GAMES     today's slate, fresh simulation
  BETS / BANK      open paper bets + bankroll
  RECORD / STATS   model accuracy ledger
  LIVE / SCORE     current live match odds, on demand
Anything else (emoji keep-alives etc.) gets no reply - no spam.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from base64 import b64encode

from .live.http import CACHE_DIR

STATE = os.path.join(CACHE_DIR, "inbox_state.json")
HELP = ("\U0001F4F1 *TEXT ME:*\n"
        "ODDS - today's predictions\n"
        "CUP - World Cup title odds\n"
        "BETS - open bets + bankroll\n"
        "RECORD - model accuracy\n"
        "LIVE - live match odds now\n"
        "(anything else just keeps daily delivery alive)")


def _twilio_get(path_qs):
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    if not (sid and tok):
        return None
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path_qs}"
    req = urllib.request.Request(url, headers={
        "Authorization": "Basic " + b64encode(f"{sid}:{tok}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except Exception:
        return None


def _load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(st):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f)


def fetch_new_inbound(phone):
    """Inbound WhatsApp messages we haven't handled yet, oldest first.
    Every processed message SID is remembered, so a message can never
    be answered twice regardless of ordering or concurrent runs. The
    very first call fast-forwards past history without replying."""
    frm = urllib.parse.quote(f"whatsapp:{phone}")
    data = _twilio_get(f"Messages.json?From={frm}&PageSize=20")
    if not data:
        return []
    msgs = [m for m in data.get("messages", [])
            if m.get("direction") == "inbound"]
    msgs.reverse()
    st = _load_state()
    if "done_sids" not in st and "last_sid" not in st:
        st["done_sids"] = [m["sid"] for m in msgs]
        _save_state(st)
        return []
    done = set(st.get("done_sids", []))
    if st.get("last_sid"):                  # migrate old single-sid state
        done.add(st["last_sid"])
    return [m for m in msgs if m["sid"] not in done]


def mark_done(sid):
    st = _load_state()
    done = st.get("done_sids", [])
    if st.get("last_sid") and st["last_sid"] not in done:
        done.append(st.pop("last_sid"))
    done.append(sid)
    st["done_sids"] = done[-300:]
    _save_state(st)


def _answer(cmd, n_sims=100_000):
    from . import learn, paper
    from .data.worldcup2026 import get_team, get_context, FIXTURES
    from .notify import build_message
    from .simulator import simulate_match

    if cmd in ("menu", "help", "commands"):
        return HELP

    if cmd in ("bets", "bank", "bankroll", "bet"):
        st = paper._load()
        if st["open"]:
            return (paper.build_bet_slip(st["open"], title="OPEN PAPER BETS")
                    + "\n\U0001F4C8 " + paper.summary_line())
        return "\U0001F4B0 No open bets.\n" + paper.summary_line()

    if cmd in ("record", "stats", "history"):
        st = learn.load_state()
        lines = ["\U0001F4CA *MODEL LEDGER*"]
        for h in st["history"][-6:]:
            mark = "✓" if h["called"] else "✗" if h["called"] is not None else "~"
            lines.append(f"{mark} {h['match']} (had home "
                         f"{h['predicted_home']:.0%})")
        lines.append(learn.record_line())
        lines.append(paper.summary_line())
        return "\n".join(lines)

    if cmd in ("odds", "games", "today", "predictions"):
        results = []
        for h, a in FIXTURES:
            ta, tb = get_team(h), get_team(a)
            if learn.is_settled(ta.code, tb.code):
                continue
            results.append(simulate_match(ta, tb, n_sims=n_sims,
                                          context=get_context(h, a)))
        if not results:
            return "No upcoming fixtures in the model right now."
        return build_message(results, include_other=False)

    if cmd in ("cup", "winner", "title", "champ", "champion"):
        from .tournament import title_message
        return title_message()

    if cmd in ("live", "score", "scores"):
        from .inplay import run_live_update
        for h, a in FIXTURES:
            outcome = run_live_update(h, a, n_sims=200_000, force=True)
            if outcome in ("live-sent", "goal-sent"):
                return None               # update already sent directly
        return "No match is live right now."

    return None                            # unrecognized: stay silent


def process(n_sims=100_000):
    """Poll for new replies, answer commands. Returns list of actions."""
    phone = os.environ.get("PREDICTOR_PHONE", "")
    if not phone:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(root, "phone.txt")
        if os.path.exists(p):
            with open(p) as f:
                phone = f.read().strip()
    if not phone:
        return ["inbox: no phone configured"]

    import re
    from .live.http import flock

    actions = []
    with flock("inbox"):
        msgs = fetch_new_inbound(phone)
        for m in msgs:
            mark_done(m["sid"])
            body = (m.get("body") or "").strip().lower()
            first = body.split()[0] if body.split() else ""
            cmd = re.sub(r"[^a-z]", "", first)   # 'Cup?' / ' ODDS!' -> cmd
            try:
                reply = _answer(cmd, n_sims=n_sims)
            except Exception as e:
                reply = None
                actions.append(f"inbox: '{cmd}' failed ({e})")
            if reply:
                from .notify import send_long
                ok, _, detail = send_long(phone, reply)
                actions.append(f"inbox: answered '{cmd}'"
                               + ("" if ok else f" SEND FAILED: {detail}"))
            elif body:
                actions.append(f"inbox: ignored '{body[:20]}'")
    return actions
