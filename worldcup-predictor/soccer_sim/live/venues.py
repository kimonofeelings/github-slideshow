"""The sixteen real 2026 World Cup stadiums: coordinates, altitude, roof.

Venue facts are fixed for the tournament, so shipping them as data is
both faster and more reliable than geocoding on every run. Live fixture
lookups return a venue name; `find_venue()` resolves it here (handling
sponsor renames like Estadio Azteca -> Estadio Banorte). Unknown venues
fall back to Open-Meteo's geocoder in enrich.py.
"""

VENUES = {
    "estadio azteca":            dict(lat=19.3029, lon=-99.1505, altitude_m=2240, roof=False, city="Mexico City"),
    "estadio banorte":           dict(lat=19.3029, lon=-99.1505, altitude_m=2240, roof=False, city="Mexico City"),
    "estadio akron":             dict(lat=20.6817, lon=-103.4626, altitude_m=1580, roof=False, city="Guadalajara"),
    "estadio guadalajara":       dict(lat=20.6817, lon=-103.4626, altitude_m=1580, roof=False, city="Guadalajara"),
    "estadio bbva":              dict(lat=25.6690, lon=-100.2439, altitude_m=540,  roof=False, city="Monterrey"),
    "estadio monterrey":         dict(lat=25.6690, lon=-100.2439, altitude_m=540,  roof=False, city="Monterrey"),
    "mercedes-benz stadium":     dict(lat=33.7554, lon=-84.4010,  altitude_m=320,  roof=True,  city="Atlanta"),
    "atlanta stadium":           dict(lat=33.7554, lon=-84.4010,  altitude_m=320,  roof=True,  city="Atlanta"),
    "metlife stadium":           dict(lat=40.8135, lon=-74.0745,  altitude_m=3,    roof=False, city="East Rutherford"),
    "new york new jersey stadium": dict(lat=40.8135, lon=-74.0745, altitude_m=3,   roof=False, city="East Rutherford"),
    "at&t stadium":              dict(lat=32.7473, lon=-97.0945,  altitude_m=168,  roof=True,  city="Arlington"),
    "dallas stadium":            dict(lat=32.7473, lon=-97.0945,  altitude_m=168,  roof=True,  city="Arlington"),
    "hard rock stadium":         dict(lat=25.9580, lon=-80.2389,  altitude_m=3,    roof=False, city="Miami Gardens"),
    "miami stadium":             dict(lat=25.9580, lon=-80.2389,  altitude_m=3,    roof=False, city="Miami Gardens"),
    "sofi stadium":              dict(lat=33.9535, lon=-118.3392, altitude_m=30,   roof=True,  city="Inglewood"),
    "los angeles stadium":       dict(lat=33.9535, lon=-118.3392, altitude_m=30,   roof=True,  city="Inglewood"),
    "lumen field":               dict(lat=47.5952, lon=-122.3316, altitude_m=5,    roof=False, city="Seattle"),
    "seattle stadium":           dict(lat=47.5952, lon=-122.3316, altitude_m=5,    roof=False, city="Seattle"),
    "levi's stadium":            dict(lat=37.4033, lon=-121.9694, altitude_m=3,    roof=False, city="Santa Clara"),
    "san francisco bay area stadium": dict(lat=37.4033, lon=-121.9694, altitude_m=3, roof=False, city="Santa Clara"),
    "geha field at arrowhead stadium": dict(lat=39.0489, lon=-94.4839, altitude_m=265, roof=False, city="Kansas City"),
    "arrowhead stadium":         dict(lat=39.0489, lon=-94.4839,  altitude_m=265,  roof=False, city="Kansas City"),
    "kansas city stadium":       dict(lat=39.0489, lon=-94.4839,  altitude_m=265,  roof=False, city="Kansas City"),
    "nrg stadium":               dict(lat=29.6847, lon=-95.4107,  altitude_m=15,   roof=True,  city="Houston"),
    "houston stadium":           dict(lat=29.6847, lon=-95.4107,  altitude_m=15,   roof=True,  city="Houston"),
    "lincoln financial field":   dict(lat=39.9008, lon=-75.1675,  altitude_m=12,   roof=False, city="Philadelphia"),
    "philadelphia stadium":      dict(lat=39.9008, lon=-75.1675,  altitude_m=12,   roof=False, city="Philadelphia"),
    "gillette stadium":          dict(lat=42.0909, lon=-71.2643,  altitude_m=89,   roof=False, city="Foxborough"),
    "boston stadium":            dict(lat=42.0909, lon=-71.2643,  altitude_m=89,   roof=False, city="Foxborough"),
    "bmo field":                 dict(lat=43.6332, lon=-79.4189,  altitude_m=83,   roof=False, city="Toronto"),
    "toronto stadium":           dict(lat=43.6332, lon=-79.4189,  altitude_m=83,   roof=False, city="Toronto"),
    "bc place":                  dict(lat=49.2768, lon=-123.1120, altitude_m=5,    roof=True,  city="Vancouver"),
    "bc place stadium":          dict(lat=49.2768, lon=-123.1120, altitude_m=5,    roof=True,  city="Vancouver"),
    "vancouver stadium":         dict(lat=49.2768, lon=-123.1120, altitude_m=5,    roof=True,  city="Vancouver"),
}


def find_venue(name):
    """Resolve a venue name (as returned by a fixtures API) to venue facts."""
    if not name:
        return None
    return VENUES.get(name.strip().lower())
