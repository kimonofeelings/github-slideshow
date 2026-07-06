"""Text-message delivery: predictions straight to your phone.

`sms_summary()` compresses one or more simulation results into a compact
SMS (winners, probabilities, expected goals, most likely scoreline, top
scorers, standout conditions). `send_sms()` delivers it through the
first available provider:

  1. Twilio            TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM
  2. Email->SMS        SMS_SMTP_HOST/PORT/USER/PASS + SMS_CARRIER_GATEWAY
                       (e.g. vtext.com, txt.att.net, tmomail.net)
  3. TextBelt          works OUT OF THE BOX: the shared free key
                       ("textbelt") sends 1 free US/Canada text per day.
                       Set TEXTBELT_KEY to a purchased key for more.

All senders are stdlib-only. TextBelt is always available as the
zero-config default; --text-preview shows the exact message first.
"""

import json
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from email.mime.text import MIMEText


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------
def _match_line(res):
    fc = res.forecast
    A, B = fc.home.team, fc.away.team
    if res.knockout and res.p_home_advance:
        if res.p_home_advance >= 0.5:
            win, lose, p = A, B, res.p_home_advance
        else:
            win, lose, p = B, A, res.p_away_advance
        head = f"{win.code} over {lose.code} {p:.0%}"
    else:
        head = (f"{A.code} {res.p_home_win:.0%} / draw {res.p_draw:.0%} / "
                f"{B.code} {res.p_away_win:.0%}")

    h, a, sp = res.top_scorelines[0]
    top_a = res.scorers_home[0]
    top_b = res.scorers_away[0]
    bits = [
        head,
        f"xG {res.avg_goals_home_90:.1f}-{res.avg_goals_away_90:.1f}",
        f"likely {A.code} {h}-{a} ({sp:.0%})",
        f"scorers {top_a['name'].split()[-1]} {top_a['anytime']:.0%} & "
        f"{top_b['name'].split()[-1]} {top_b['anytime']:.0%}",
    ]
    if res.knockout and res.p_penalties > 0.10:
        bits.insert(1, f"pens {res.p_penalties:.0%}")

    ctx = fc.context
    if ctx is not None:
        flags = []
        if ctx.rain > 0.3:
            flags.append("rain")
        if ctx.altitude_m >= 1500:
            flags.append(f"{ctx.altitude_m}m alt")
        if not ctx.roof_closed and ctx.temp_c >= 30:
            flags.append(f"{ctx.temp_c:.0f}C heat")
        venue = ctx.venue.replace(" Stadium", "")
        bits.append("@ " + venue + (f" ({', '.join(flags)})" if flags else ""))
    return " | ".join(bits)


def sms_summary(results, extra=None):
    """One compact text for a list of SimulationResult objects."""
    stamp = datetime.now(timezone.utc).strftime("%b %d %H:%M UTC")
    lines = [f"WC26 PREDICTOR - {stamp}"]
    for res in results:
        lines.append(_match_line(res))
    for line in extra or []:
        lines.append(line)
    lines.append(f"({results[0].n_sims:,} sims/match)")
    return "\n".join(lines)


FLAGS = {"ARG": "\U0001F1E6\U0001F1F7", "EGY": "\U0001F1EA\U0001F1EC",
         "BRA": "\U0001F1E7\U0001F1F7", "NOR": "\U0001F1F3\U0001F1F4",
         "MEX": "\U0001F1F2\U0001F1FD",
         "ENG": "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E"
                "\U000E0067\U000E007F"}


def _flag(code):
    return FLAGS.get(code, "\U0001F3F3️")


def _kickoff_pacific(ctx):
    """'2026-07-06 00:00 UTC' -> 'Sun 5:00 PM PT' (best effort)."""
    if not ctx or not ctx.kickoff_local or "UTC" not in ctx.kickoff_local:
        return None
    try:
        from zoneinfo import ZoneInfo
        dt = datetime.strptime(ctx.kickoff_local[:16], "%Y-%m-%d %H:%M")
        dt = dt.replace(tzinfo=timezone.utc).astimezone(
            ZoneInfo("America/Los_Angeles"))
        return dt.strftime("%a %-I:%M %p PT").replace(" 0:", " 12:")
    except Exception:
        return None


def _key_battle(fc):
    """The most lopsided attacking zone in the match - the matchup that
    drives the forecast more than any other."""
    best = None
    for tf, opp in ((fc.home, fc.away), (fc.away, fc.home)):
        for zb in tf.zones.values():
            if best is None or zb.multiplier > best[0].multiplier:
                best = (zb, tf.team)
    zb, team = best
    if zb.multiplier < 1.12 or not zb.key_attackers or not zb.key_defenders:
        return None
    return (f"\U0001F511 {zb.key_attackers[0][0]} vs "
            f"{zb.key_defenders[0][0]}'s zone (edge x{zb.multiplier:.2f} "
            f"to {team.name})")


def whatsapp_summary(results, extra=None):
    """Rich, sectioned message using WhatsApp *bold* and emoji."""
    stamp = datetime.now(timezone.utc).strftime("%A, %b %d")
    lines = [f"⚽ *WORLD CUP PREDICTOR* — {stamp}", ""]
    for res in results:
        fc = res.forecast
        A, B = fc.home.team, fc.away.team
        lines.append(f"{_flag(A.code)} *{A.name} vs {B.name}* {_flag(B.code)}")

        ctx = fc.context
        if ctx is not None:
            flags = []
            ko = _kickoff_pacific(ctx)
            if ko:
                flags.append(ko)
            if ctx.roof_closed:
                flags.append("roof closed")
            else:
                flags.append(f"{ctx.temp_c:.0f}°C")
                if ctx.rain > 0.3:
                    flags.append("\U0001F327️ rain")
            if ctx.altitude_m >= 1500:
                flags.append(f"⛰️ {ctx.altitude_m:,}m altitude")
            lines.append(f"\U0001F3DF {ctx.venue} ({', '.join(flags)})")

        if res.p_home_advance >= 0.5:
            win, p = A, res.p_home_advance
        else:
            win, p = B, res.p_away_advance
        upset = "  ⚠️ coin-flip territory" if p < 0.60 else ""
        lines.append(f"\U0001F52E *{win.name} to advance: {p:.0%}*"
                     + (f"  (pens {res.p_penalties:.0%})"
                        if res.p_penalties > 0.10 else "") + upset)
        h, a, sp = res.top_scorelines[0]
        lines.append(f"⚽ Goals {res.avg_goals_home_90:.1f} - "
                     f"{res.avg_goals_away_90:.1f}  |  most likely "
                     f"*{h}-{a}* ({sp:.0%})")
        ta, tb = res.scorers_home[0], res.scorers_away[0]
        lines.append(f"⭐ {ta['name']} {ta['anytime']:.0%}  |  "
                     f"{tb['name']} {tb['anytime']:.0%}")
        battle = _key_battle(fc)
        if battle:
            lines.append(battle)
        lines.append("")
    for line in extra or []:
        lines.append(f"\U0001F4C8 {line}")
    if extra:
        lines.append("")
    lines.append(f"_{results[0].n_sims:,} simulations per match, live venue "
                 f"& weather data_")
    lines.append("_Reply anything to keep daily delivery active_")
    return "\n".join(lines)


COUNTRY_FLAGS = {
    "portugal": "\U0001F1F5\U0001F1F9", "spain": "\U0001F1EA\U0001F1F8",
    "united states": "\U0001F1FA\U0001F1F8", "belgium": "\U0001F1E7\U0001F1EA",
    "switzerland": "\U0001F1E8\U0001F1ED", "colombia": "\U0001F1E8\U0001F1F4",
    "france": "\U0001F1EB\U0001F1F7", "morocco": "\U0001F1F2\U0001F1E6",
    "argentina": "\U0001F1E6\U0001F1F7", "egypt": "\U0001F1EA\U0001F1EC",
    "brazil": "\U0001F1E7\U0001F1F7", "norway": "\U0001F1F3\U0001F1F4",
    "mexico": "\U0001F1F2\U0001F1FD", "england": FLAGS["ENG"],
    "germany": "\U0001F1E9\U0001F1EA", "netherlands": "\U0001F1F3\U0001F1F1",
    "japan": "\U0001F1EF\U0001F1F5", "senegal": "\U0001F1F8\U0001F1F3",
    "croatia": "\U0001F1ED\U0001F1F7", "uruguay": "\U0001F1FA\U0001F1FE",
    "italy": "\U0001F1EE\U0001F1F9", "canada": "\U0001F1E8\U0001F1E6",
}


def other_matches_section(modeled_names):
    """Market-implied lines for every upcoming World Cup game that the
    player-level model doesn't cover. Probabilities come from Polymarket
    advancement prices, normalized head-to-head."""
    from .live.espn import fetch_upcoming
    from .paper import fetch_advance_prices
    fixtures = fetch_upcoming()
    prices = fetch_advance_prices()
    # ESPN display names -> Polymarket market names
    aliases = {"united states": "usa", "turkey": "turkiye",
               "czech republic": "czechia", "south korea": "south korea",
               "côte d'ivoire": "ivory coast"}
    lines = []
    for fx in fixtures:
        h, a = fx["home"], fx["away"]
        if {h.lower(), a.lower()} & modeled_names:
            continue
        if fx["state"] == "post":
            continue
        ph = prices.get(aliases.get(h.lower(), h.lower()))
        pa = prices.get(aliases.get(a.lower(), a.lower()))
        when = ""
        try:
            from zoneinfo import ZoneInfo
            dt = datetime.fromisoformat(fx["date_utc"].replace("Z", "+00:00"))
            dt = dt.astimezone(ZoneInfo("America/Los_Angeles"))
            when = dt.strftime("%a %-I:%M%p PT ").replace("AM", "am").replace("PM", "pm")
        except Exception:
            pass
        fh = COUNTRY_FLAGS.get(h.lower(), "")
        fa = COUNTRY_FLAGS.get(a.lower(), "")
        if ph and pa and (ph + pa) > 0.1:
            p = ph / (ph + pa)
            lead, pl = (h, p) if p >= 0.5 else (a, 1 - p)
            lines.append(f"{when}{fh} {h} vs {a} {fa} — *{lead} {pl:.0%}*")
        else:
            lines.append(f"{when}{fh} {h} vs {a} {fa}")
    if not lines:
        return []
    return ["\U0001F4C5 *OTHER GAMES* (market odds — no rosters yet)"] + lines


def build_message(results, extra=None, include_other=True):
    """Pick the format for the provider that will actually deliver:
    rich for WhatsApp, compact for plain SMS."""
    modeled = set()
    for res in results:
        modeled.add(res.forecast.home.team.name.lower())
        modeled.add(res.forecast.away.team.name.lower())
    if os.environ.get("TWILIO_WHATSAPP_FROM"):
        msg = whatsapp_summary(results, extra)
        if include_other:
            section = other_matches_section(modeled)
            if section:
                head, _, tail = msg.partition("\n_")
                candidate = head + "\n" + "\n".join(section) + "\n\n_" + tail
                if len(candidate) < 1500:      # Twilio hard cap is 1600
                    msg = candidate
        if len(msg) >= 1550:
            # trim the footer lines first, then key-battle lines
            msg = msg.replace("\n_1,000,000 simulations per match, live "
                              "venue & weather data_", "")
            if len(msg) >= 1550:
                msg = "\n".join(l for l in msg.split("\n")
                                if not l.startswith("\U0001F511"))
        return msg
    return sms_summary(results, extra)


# --------------------------------------------------------------------------
# providers (stdlib only)
# --------------------------------------------------------------------------
def _post_form(url, fields, headers=None, timeout=20):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def _send_twilio(phone, message, whatsapp=False):
    sid = os.environ.get("TWILIO_ACCOUNT_SID")      # ACxxxx (always needed)
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    key = os.environ.get("TWILIO_API_KEY")           # SKxxxx (alternative
    secret = os.environ.get("TWILIO_API_SECRET")     #  auth via API key)
    src = (os.environ.get("TWILIO_WHATSAPP_FROM") if whatsapp
           else os.environ.get("TWILIO_FROM"))
    if not (sid and src and (tok or (key and secret))):
        return None
    to = phone
    if whatsapp:
        # WhatsApp sandbox: both sides carry the whatsapp: prefix
        if not src.startswith("whatsapp:"):
            src = "whatsapp:" + src
        to = "whatsapp:" + phone
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    user, pw = (key, secret) if key and secret else (sid, tok)
    auth = b64encode(f"{user}:{pw}".encode()).decode()
    try:
        body = _post_form(url, {"To": to, "From": src, "Body": message},
                          headers={"Authorization": f"Basic {auth}"})
    except urllib.error.HTTPError as e:
        # Twilio explains rejections (bad creds, unverified number, ...)
        # in the response body - surface that, not just the status code.
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except ValueError:
            pass
        return f"twilio said: HTTP {e.code}: {detail[:200]}"
    try:
        data = json.loads(body)
    except ValueError:
        return f"twilio said: unparseable response: {body[:160]}"
    if data.get("error_code") is None and \
            data.get("status") in ("queued", "accepted", "sending", "sent"):
        return "sent"
    return (f"twilio said: status={data.get('status')} "
            f"error={data.get('error_code')} {data.get('error_message')}")


def _send_textbelt(phone, message):
    # "textbelt" is the provider's shared free key: 1 US/Canada text/day.
    key = os.environ.get("TEXTBELT_KEY", "textbelt")
    body = _post_form("https://textbelt.com/text",
                      {"phone": phone, "message": message, "key": key})
    if '"success":true' in body.replace(" ", ""):
        return "sent"
    return f"textbelt said: {body[:160]}"


def _send_email_gateway(phone, message):
    host = os.environ.get("SMS_SMTP_HOST")
    user = os.environ.get("SMS_SMTP_USER")
    pw = os.environ.get("SMS_SMTP_PASS")
    gateway = os.environ.get("SMS_CARRIER_GATEWAY")
    if not (host and user and pw and gateway):
        return None
    port = int(os.environ.get("SMS_SMTP_PORT", "587"))
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    to = f"{digits}@{gateway}"
    msg = MIMEText(message)
    msg["From"], msg["To"], msg["Subject"] = user, to, ""
    with smtplib.SMTP(host, port, timeout=25) as s:
        s.starttls()
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    return "sent"


def _send_twilio_whatsapp(phone, message):
    return _send_twilio(phone, message, whatsapp=True)


# Explicitly-configured providers first; TextBelt last because its shared
# free key always "qualifies" and should not shadow a real Twilio setup.
# WhatsApp (sandbox: no number verification needed) beats plain SMS when
# TWILIO_WHATSAPP_FROM is set, since unverified SMS numbers get blocked.
PROVIDERS = [("Twilio WhatsApp", _send_twilio_whatsapp),
             ("Twilio", _send_twilio),
             ("Email->SMS gateway", _send_email_gateway),
             ("TextBelt", _send_textbelt)]

UPGRADE_HINT = """Free-tier tips:
  - TextBelt's shared free key sends 1 US/Canada text per day; a purchased
    key (TEXTBELT_KEY) removes the limit.
  - For unlimited/reliable delivery use a free Twilio trial:
    export TWILIO_ACCOUNT_SID=ACxxxx TWILIO_AUTH_TOKEN=xxxx TWILIO_FROM=+1555...
  - Or your carrier's free email gateway (Gmail app password):
    export SMS_SMTP_HOST=smtp.gmail.com SMS_SMTP_USER=you@gmail.com \\
           SMS_SMTP_PASS=app-password SMS_CARRIER_GATEWAY=vtext.com"""


def send_sms(phone, message):
    """Try providers in order. Returns (ok, provider, detail)."""
    tried = []
    for name, fn in PROVIDERS:
        try:
            outcome = fn(phone, message)
        except Exception as e:
            tried.append(f"{name}: failed ({e})")
            continue
        if outcome is None:
            continue                      # not configured, try next
        if outcome == "sent":
            return True, name, "delivered to " + phone
        tried.append(f"{name}: {outcome}")
    return False, None, "; ".join(tried) + "\n" + UPGRADE_HINT
