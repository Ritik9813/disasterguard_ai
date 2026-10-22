"""Locations, data collection (Open-Meteo + USGS, with offline demo scenarios) and the risk engine.

The risk engine is a transparent rule-based scorer, not a trained ML model.
"""
import hashlib
import math
import random
from datetime import date, datetime, timezone

import requests

HAZARDS = ["Flood", "Cyclone", "Landslide", "Earthquake", "Forest Fire", "Heatwave"]
LEVEL_COLOR = {"Very High": "#D62828", "High": "#F77F00", "Moderate": "#FCBF49", "Low": "#4CAF50"}
TAG_HAZARD = {"flood": "Flood", "cyclone": "Cyclone", "landslide": "Landslide",
              "quake": "Earthquake", "fire": "Forest Fire", "heat": "Heatwave"}


def _c(name, state, lat, lon, pop_lakh, tags):
    return dict(name=name, state=state, lat=lat, lon=lon, pop_lakh=pop_lakh, tags=tags.split())


# pop_lakh is a rough metro-area figure, used only for indicative estimates
LOCATIONS = [
    _c("Patna", "Bihar", 25.61, 85.14, 20, "flood quake"),
    _c("Guwahati", "Assam", 26.14, 91.74, 11, "flood landslide quake"),
    _c("Bhubaneswar", "Odisha", 20.30, 85.82, 12, "cyclone flood"),
    _c("Kolkata", "West Bengal", 22.57, 88.36, 150, "cyclone flood"),
    _c("Chennai", "Tamil Nadu", 13.08, 80.27, 120, "cyclone flood"),
    _c("Visakhapatnam", "Andhra Pradesh", 17.69, 83.22, 20, "cyclone"),
    _c("Mumbai", "Maharashtra", 19.08, 72.88, 200, "flood cyclone"),
    _c("Surat", "Gujarat", 21.17, 72.83, 80, "flood cyclone"),
    _c("Dehradun", "Uttarakhand", 30.32, 78.03, 8, "landslide quake fire"),
    _c("Shimla", "Himachal Pradesh", 31.10, 77.17, 2, "landslide quake fire"),
    _c("Srinagar", "Jammu & Kashmir", 34.08, 74.80, 15, "flood quake landslide"),
    _c("Delhi", "Delhi", 28.61, 77.21, 300, "quake heat"),
    _c("Lucknow", "Uttar Pradesh", 26.85, 80.95, 40, "flood heat"),
    _c("Jaipur", "Rajasthan", 26.91, 75.79, 40, "heat"),
    _c("Bhopal", "Madhya Pradesh", 23.26, 77.41, 20, "heat fire"),
    _c("Hyderabad", "Telangana", 17.39, 78.48, 100, "flood"),
    _c("Bengaluru", "Karnataka", 12.97, 77.59, 130, "flood"),
    _c("Kochi", "Kerala", 9.93, 76.27, 22, "flood landslide"),
    _c("Ludhiana", "Punjab", 30.90, 75.86, 18, "flood heat"),
    _c("Ranchi", "Jharkhand", 23.34, 85.31, 11, "fire heat"),
    _c("Raipur", "Chhattisgarh", 21.25, 81.63, 12, "fire heat"),
    _c("Gangtok", "Sikkim", 27.33, 88.61, 1, "landslide quake"),
]

_QUAKE_MINOR = [
    {"place": "Andaman Sea", "mag": 4.2, "lat": 11.0, "lon": 93.0, "depth": 10, "hours_ago": 7},
    {"place": "Near Leh, Ladakh", "mag": 3.1, "lat": 34.2, "lon": 77.6, "depth": 12, "hours_ago": 19},
]

SCENARIOS = {
    "Normal day": {"states": (), "ranges": {}},
    "Monsoon floods": {
        "states": ("Bihar", "Assam", "West Bengal", "Uttar Pradesh", "Odisha", "Jharkhand"),
        "ranges": dict(rain_today=(70, 150), rain_prev3d=(110, 240), rain_next2d=(90, 180), river_rise=(1.8, 3.2))},
    "Cyclone landfall": {
        "states": ("Odisha", "Andhra Pradesh", "West Bengal", "Tamil Nadu"),
        "ranges": dict(wind_max=(85, 140), rain_today=(40, 90), rain_prev3d=(20, 60), rain_next2d=(110, 200))},
    "Himalayan landslides": {
        "states": ("Uttarakhand", "Himachal Pradesh", "Sikkim", "Jammu & Kashmir", "Assam"),
        "ranges": dict(rain_today=(60, 140), rain_prev3d=(100, 220), rain_next2d=(80, 160))},
    "Heatwave": {
        "states": ("Delhi", "Rajasthan", "Uttar Pradesh", "Madhya Pradesh", "Chhattisgarh", "Jharkhand", "Punjab"),
        "ranges": dict(temp_max=(43, 48), rain_today=(0, 0.5), rain_prev3d=(0, 1), rain_next2d=(0, 1))},
    "Earthquake": {
        "states": (), "ranges": {},
        "quakes": [{"place": "Near Dehradun, Uttarakhand", "mag": 5.6, "lat": 30.4, "lon": 78.3, "depth": 15, "hours_ago": 3},
                   {"place": "Aftershock, Uttarakhand", "mag": 4.1, "lat": 30.5, "lon": 78.2, "depth": 12, "hours_ago": 1}]},
}


# ------------------------------------------------------------------ risk engine
def exposure(city: dict, hazard: str) -> float:
    return 1.0 if any(TAG_HAZARD[t] == hazard for t in city["tags"]) else 0.35


def level_of(score: float) -> str:
    return "Low" if score < 25 else "Moderate" if score < 50 else "High" if score < 75 else "Very High"


def score_hazard(hazard: str, f: dict, expo: float) -> float:
    """0-100 score from simple, explainable rules. f holds the weather/quake features."""
    rain_idx = f["rain_today"] + 0.4 * f["rain_prev3d"] + 0.7 * f["rain_next2d"]
    if hazard == "Flood":
        base = min(100, rain_idx / 1.8) + min(25, max(0, (f.get("river_rise", 1.0) - 1) * 25))
        s = base * (0.5 + 0.5 * expo)
    elif hazard == "Cyclone":
        s = (max(0, f["wind_max"] - 35) * 1.4 + f["rain_next2d"] * 0.15) * (0.3 + 0.7 * expo)
    elif hazard == "Landslide":
        s = min(100, rain_idx / 1.4) * (0.2 + 0.8 * expo)
    elif hazard == "Earthquake":
        mag, km = f.get("quake_mag", 0), f.get("quake_km", 999)
        s = max(0, mag - 2.5) * 22 * max(0, 1 - km / 400) * (0.5 + 0.5 * expo) if mag else 0
    elif hazard == "Forest Fire":
        dry = max(0, 12 - (f["rain_prev3d"] + f["rain_next2d"])) * 2.5
        s = (max(0, f["temp_max"] - 30) * 5 + dry) * (0.3 + 0.7 * expo)
    else:  # Heatwave
        s = max(0, f["temp_max"] - 35) * 9 * (0.6 + 0.4 * expo)
    return max(0.0, min(100.0, s))


def people_at_risk(snap: dict, hazard: str) -> int:
    frac = {"Very High": 0.10, "High": 0.04, "Moderate": 0.01, "Low": 0.0}
    return int(sum(c["pop_lakh"] * 1e5 * frac[c["levels"][hazard]] for c in snap["cities"]))


# ------------------------------------------------------------------ data sources
def haversine(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _demo_features(city: dict, scenario: str) -> dict:
    seed = int(hashlib.md5(f"{date.today()}|{city['name']}|{scenario}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    f = dict(rain_today=rng.uniform(0, 8), rain_prev3d=rng.uniform(0, 20), rain_next2d=rng.uniform(0, 15),
             wind_max=rng.uniform(12, 30), temp_max=rng.uniform(27, 36), river_rise=rng.uniform(0.9, 1.2))
    spec = SCENARIOS[scenario]
    if city["state"] in spec["states"]:
        f.update({k: rng.uniform(*v) for k, v in spec["ranges"].items()})
    return {k: round(v, 1) for k, v in f.items()}


def fetch_live_weather(cities: list) -> list:
    r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=15, params=dict(
        latitude=",".join(str(c["lat"]) for c in cities), longitude=",".join(str(c["lon"]) for c in cities),
        daily="precipitation_sum,wind_speed_10m_max,temperature_2m_max",
        past_days=3, forecast_days=3, timezone="auto"))
    r.raise_for_status()
    data = r.json()
    data = data if isinstance(data, list) else [data]
    out = []
    for d in data:
        dl = d["daily"]
        rain = [x or 0 for x in dl["precipitation_sum"]]
        wind = [x for x in dl["wind_speed_10m_max"][3:] if x is not None] or [0]
        temp = [x for x in dl["temperature_2m_max"][3:] if x is not None] or [30]
        out.append(dict(rain_today=round(rain[3], 1), rain_prev3d=round(sum(rain[:3]), 1),
                        rain_next2d=round(sum(rain[4:6]), 1), wind_max=round(max(wind), 1),
                        temp_max=round(max(temp), 1)))
    return out


def fetch_live_river_rise(cities: list):
    """Peak forecast river discharge divided by today's value. Returns None if unavailable."""
    try:
        r = requests.get("https://flood-api.open-meteo.com/v1/flood", timeout=15, params=dict(
            latitude=",".join(str(c["lat"]) for c in cities), longitude=",".join(str(c["lon"]) for c in cities),
            daily="river_discharge", forecast_days=5))
        r.raise_for_status()
        data = r.json()
        data = data if isinstance(data, list) else [data]
        rises = []
        for d in data:
            v = [x for x in d["daily"]["river_discharge"] if x is not None]
            rises.append(round(max(v[1:]) / v[0], 2) if len(v) > 1 and v[0] > 0 else 1.0)
        return rises
    except Exception:
        return None


def fetch_live_quakes() -> list:
    r = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson", timeout=15)
    r.raise_for_status()
    out = []
    now = datetime.now(timezone.utc).timestamp()
    for f in r.json()["features"]:
        lon, lat, depth = f["geometry"]["coordinates"]
        if 5 <= lat <= 38 and 67 <= lon <= 98:
            p = f["properties"]
            out.append({"place": p["place"], "mag": p["mag"], "lat": lat, "lon": lon, "depth": depth,
                        "hours_ago": round((now - p["time"] / 1000) / 3600)})
    return sorted(out, key=lambda q: -q["mag"])


def _nearest_quake(city: dict, quakes: list):
    best = (0, 999)
    for q in quakes:
        d = haversine(city["lat"], city["lon"], q["lat"], q["lon"])
        if d <= 400 and q["mag"] > best[0]:
            best = (q["mag"], round(d))
    return best


def build_snapshot(live: bool = False, scenario: str = "Normal day") -> dict:
    note, source, feats, quakes = "", "demo", None, None
    if live:
        try:
            weather = fetch_live_weather(LOCATIONS)
            rises = fetch_live_river_rise(LOCATIONS)
            quakes = fetch_live_quakes()
            feats = [{**w, "river_rise": rises[i] if rises else 1.0} for i, w in enumerate(weather)]
            source = "live"
        except Exception as e:
            note = f"Live data unavailable ({type(e).__name__}). Showing the 'Normal day' demo instead."
            scenario = "Normal day"
    if feats is None:
        feats = [_demo_features(c, scenario) for c in LOCATIONS]
        quakes = SCENARIOS[scenario].get("quakes", _QUAKE_MINOR)
    cities = []
    for c, f in zip(LOCATIONS, feats):
        qm, qkm = _nearest_quake(c, quakes)
        f = {**f, "quake_mag": qm, "quake_km": qkm}
        scores = {h: round(score_hazard(h, f, exposure(c, h)), 1) for h in HAZARDS}
        cities.append({**c, **f, "scores": scores, "levels": {h: level_of(s) for h, s in scores.items()}})
    return dict(source=source, scenario="Live data" if source == "live" else scenario, note=note,
                generated=datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
                cities=cities, quakes=quakes[:40])
