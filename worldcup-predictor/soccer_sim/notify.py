"""Text-message delivery: predictions straight to your phone.

`sms_summary()` compresses one or more simulation results into a compact
SMS (winners, probabilities, expected goals, most likely scoreline, top
scorers, standout conditions). `send_sms()` delivers it through the
first configured provider:

  1. Twilio            TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM
  2. TextBelt          TEXTBELT_KEY  ("textbelt" = shared free key, 1/day)
  3. Email->SMS        SMS_SMTP_HOST/PORT/USER/PASS + SMS_CARRIER_GATEWAY
                       (e.g. vtext.com, txt.att.net, tmomail.net)

All senders are stdlib-only. Nothing is sent unless a provider is
configured; --text-preview always shows the exact message first.
"""

import os
import smtplib
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


def sms_summary(results):
    """One compact text for a list of SimulationResult objects."""
    stamp = datetime.now(timezone.utc).strftime("%b %d %H:%M UTC")
    lines = [f"WC26 PREDICTOR - {stamp}"]
    for res in results:
        lines.append(_match_line(res))
    lines.append(f"({results[0].n_sims:,} sims/match)")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# providers (stdlib only)
# --------------------------------------------------------------------------
def _post_form(url, fields, headers=None, timeout=20):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def _send_twilio(phone, message):
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    src = os.environ.get("TWILIO_FROM")
    if not (sid and tok and src):
        return None
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    auth = b64encode(f"{sid}:{tok}".encode()).decode()
    body = _post_form(url, {"To": phone, "From": src, "Body": message},
                      headers={"Authorization": f"Basic {auth}"})
    if '"error_code": null' in body or '"status": "queued"' in body:
        return "sent"
    return f"twilio said: {body[:160]}"


def _send_textbelt(phone, message):
    key = os.environ.get("TEXTBELT_KEY")
    if not key:
        return None
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


PROVIDERS = [("Twilio", _send_twilio),
             ("TextBelt", _send_textbelt),
             ("Email->SMS gateway", _send_email_gateway)]

SETUP_HELP = """No SMS provider configured. Set one of:
  Twilio (most reliable):
    export TWILIO_ACCOUNT_SID=ACxxxx TWILIO_AUTH_TOKEN=xxxx TWILIO_FROM=+1555...
  TextBelt (quickest start; key 'textbelt' = 1 free text/day):
    export TEXTBELT_KEY=textbelt
  Email->SMS via your carrier (free, needs SMTP e.g. Gmail app password):
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
    if tried:
        return False, None, "; ".join(tried)
    return False, None, SETUP_HELP
