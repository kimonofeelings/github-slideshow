"""Kickoff weather via Open-Meteo (free, keyless, no signup).

If kickoff is within the 16-day forecast horizon we take the hourly
forecast for the kickoff hour; otherwise we fall back to current
conditions at the stadium. Open-Meteo also returns the model elevation,
a useful cross-check on the venue's altitude.
"""

from datetime import datetime, timezone

from .http import get_json

FORECAST = ("https://api.open-meteo.com/v1/forecast"
            "?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,relative_humidity_2m,precipitation,"
            "wind_speed_10m"
            "&current=temperature_2m,relative_humidity_2m,precipitation,"
            "wind_speed_10m"
            "&timezone=UTC&forecast_days=16")


def fetch_weather(lat, lon, kickoff_utc=None):
    """Returns dict(temp_c, humidity, rain, wind_kmh, elevation_m, when)
    or None if the API is unreachable. `rain` is 0..1 from mm/h."""
    data = get_json(FORECAST.format(lat=lat, lon=lon), ttl=900)
    if not data:
        return None

    picked = None
    label = "current conditions"
    if kickoff_utc:
        try:
            ko = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
            ko = ko.astimezone(timezone.utc).replace(tzinfo=None)
            times = data.get("hourly", {}).get("time", [])
            target = ko.strftime("%Y-%m-%dT%H:00")
            if target in times:
                i = times.index(target)
                h = data["hourly"]
                picked = dict(temp=h["temperature_2m"][i],
                              hum=h["relative_humidity_2m"][i],
                              precip=h["precipitation"][i],
                              wind=h["wind_speed_10m"][i])
                label = f"forecast for kickoff {target}Z"
        except (ValueError, KeyError, IndexError):
            picked = None

    if picked is None:
        c = data.get("current")
        if not c:
            return None
        picked = dict(temp=c["temperature_2m"], hum=c["relative_humidity_2m"],
                      precip=c["precipitation"], wind=c["wind_speed_10m"])

    return {
        "temp_c": float(picked["temp"]),
        "humidity": float(picked["hum"]) / 100.0,
        "rain": min(float(picked["precip"]) / 3.0, 1.0),
        "wind_kmh": float(picked["wind"]),
        "elevation_m": data.get("elevation"),
        "when": label,
    }
