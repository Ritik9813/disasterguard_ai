"""LangChain tools used by the agents."""
import math
from typing import Literal

from langchain_core.tools import tool

import data as D

HazardName = Literal["Flood", "Cyclone", "Landslide", "Earthquake", "Forest Fire", "Heatwave"]


@tool
def compute_risk_score(hazard: HazardName, rain_today_mm: float = 0, rain_prev3d_mm: float = 0,
                       rain_next2d_mm: float = 0, wind_kmh: float = 20, temp_c: float = 32,
                       river_rise: float = 1.0, quake_magnitude: float = 0, quake_distance_km: float = 999,
                       exposure: float = 0.7) -> dict:
    """What-if risk score (0-100) for a hazard from raw conditions. exposure is 0-1 (1 = highly prone area)."""
    f = dict(rain_today=rain_today_mm, rain_prev3d=rain_prev3d_mm, rain_next2d=rain_next2d_mm, wind_max=wind_kmh,
             temp_max=temp_c, river_rise=river_rise, quake_mag=quake_magnitude, quake_km=quake_distance_km)
    s = D.score_hazard(hazard, f, exposure)
    return {"hazard": hazard, "score": round(s, 1), "level": D.level_of(s)}


@tool
def allocate_resources(people_at_risk: int, hazard: HazardName = "Flood", days: int = 3) -> dict:
    """Indicative rescue, medical, shelter and supply needs for a number of people at risk."""
    p = max(0, int(people_at_risk))
    return {
        "rescue_teams": math.ceil(p / 5000),
        "boats": math.ceil(p / 8000) if hazard in ("Flood", "Cyclone") else 0,
        "medical_teams": math.ceil(p / 10000),
        "relief_shelters": math.ceil(p / 500),
        "food_packets": p * days * 2,
        "drinking_water_litres": p * days * 5,
        "assumptions": "1 rescue team per 5,000 people, 1 medical team per 10,000, shelters of 500, "
                       "2 food packets and 5 litres of water per person per day. Indicative only.",
    }


@tool
def estimate_relief_needs(houses_damaged: int, road_km_damaged: float = 0, people_affected: int = 0,
                          cost_per_house_lakh: float = 2.0, cost_per_road_km_lakh: float = 40.0) -> dict:
    """Indicative recovery needs and cost (INR crore) after a disaster. Costs are adjustable assumptions."""
    houses = houses_damaged * cost_per_house_lakh / 100
    roads = road_km_damaged * cost_per_road_km_lakh / 100
    return {
        "temporary_shelter_kits": houses_damaged,
        "housing_cost_crore": round(houses, 2),
        "road_cost_crore": round(roads, 2),
        "total_cost_crore": round(houses + roads, 2),
        "livelihood_support_households": int(people_affected / 4.5),
        "assumptions": f"Rs {cost_per_house_lakh} lakh per house, Rs {cost_per_road_km_lakh} lakh per km of road, "
                       "4.5 people per household. Indicative only; replace with official assessment figures.",
    }


@tool
def emergency_contacts() -> dict:
    """Common Indian emergency numbers. Tell people to confirm local numbers with their State Disaster
    Management Authority."""
    return {"Unified emergency": "112", "Disaster management helpline": "1078", "Ambulance": "108",
            "Police": "100", "Fire": "101", "note": "Confirm local control-room numbers with your SDMA."}


STATIC = {t.name: t for t in [compute_risk_score, allocate_resources, estimate_relief_needs, emergency_contacts]}


def make_data_tools(snap: dict) -> dict:
    """Tools bound to the current data snapshot."""

    @tool
    def lookup_location_risk(city: str) -> dict:
        """Current weather features and risk scores for all hazards in one monitored city."""
        q = city.lower().split(",")[0].strip()
        for c in snap["cities"]:
            if q in c["name"].lower():
                keys = ("rain_today", "rain_prev3d", "rain_next2d", "wind_max", "temp_max", "river_rise",
                        "quake_mag", "quake_km")
                return {"city": c["name"], "state": c["state"], "population_lakh_approx": c["pop_lakh"],
                        "features": {k: c[k] for k in keys}, "scores": c["scores"], "levels": c["levels"]}
        return {"error": f"'{city}' is not monitored", "monitored": [c["name"] for c in snap["cities"]]}

    @tool
    def list_top_risks(hazard: HazardName, n: int = 5) -> dict:
        """The n monitored cities with the highest risk score for a hazard."""
        rows = sorted(snap["cities"], key=lambda c: -c["scores"][hazard])[:n]
        return {"hazard": hazard, "top": [{"city": c["name"], "state": c["state"], "score": c["scores"][hazard],
                                           "level": c["levels"][hazard]} for c in rows]}

    @tool
    def recent_earthquakes(min_magnitude: float = 3.0) -> dict:
        """Recent earthquakes in and around India at or above a magnitude."""
        q = [x for x in snap["quakes"] if x["mag"] >= min_magnitude]
        return {"count": len(q), "quakes": q[:8]}

    return {t.name: t for t in [lookup_location_risk, list_top_risks, recent_earthquakes]}


DYNAMIC_FOR = {
    "data": ("lookup_location_risk", "list_top_risks", "recent_earthquakes"),
    "predict": ("lookup_location_risk", "list_top_risks"),
    "alert": ("lookup_location_risk",),
    "response": ("lookup_location_risk", "list_top_risks"),
    "recovery": (),
}


def dynamic_tools(snap: dict, agent_key: str) -> list:
    d = make_data_tools(snap)
    return [d[n] for n in DYNAMIC_FOR.get(agent_key, ())]
