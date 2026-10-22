"""Offline tests (no API key or internet needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessageChunk

import agents
import data as D
import storage
import tools as T


class FakeLLM:
    def bind_tools(self, tools):
        return self

    def stream(self, messages):
        if not any(m.type == "tool" for m in messages):
            yield AIMessageChunk(content="", tool_calls=[{"name": "allocate_resources", "args": {"people_at_risk": 12000, "hazard": "Flood"}, "id": "1"}])
        else:
            yield AIMessageChunk(content="Deploy ")
            yield AIMessageChunk(content="3 teams.")


def test_floods_scenario_flags_patna():
    s = D.build_snapshot(False, "Monsoon floods")
    patna = next(c for c in s["cities"] if c["name"] == "Patna")
    assert patna["levels"]["Flood"] == "Very High"


def test_normal_day_is_calm_and_deterministic():
    a, b = D.build_snapshot(False, "Normal day"), D.build_snapshot(False, "Normal day")
    assert all(c["levels"][h] == "Low" for c in a["cities"] for h in D.HAZARDS)
    assert a["cities"] == b["cities"]


def test_earthquake_scenario_raises_dehradun():
    s = D.build_snapshot(False, "Earthquake")
    d = next(c for c in s["cities"] if c["name"] == "Dehradun")
    assert d["levels"]["Earthquake"] in ("High", "Very High")


def test_live_failure_falls_back(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(D.requests, "get", boom)
    s = D.build_snapshot(True, "Monsoon floods")
    assert s["source"] == "demo" and "unavailable" in s["note"] and s["scenario"] == "Normal day"


def test_tools():
    r = T.allocate_resources.invoke({"people_at_risk": 10000, "hazard": "Flood"})
    assert r["rescue_teams"] == 2 and r["boats"] == 2 and r["relief_shelters"] == 20
    assert T.allocate_resources.invoke({"people_at_risk": 0})["rescue_teams"] == 0
    c = T.estimate_relief_needs.invoke({"houses_damaged": 100, "road_km_damaged": 10})
    assert c["total_cost_crore"] == 6.0
    w = T.compute_risk_score.invoke({"hazard": "Heatwave", "temp_c": 46, "exposure": 1})
    assert w["level"] in ("High", "Very High")


def test_dynamic_tools_lookup():
    s = D.build_snapshot(False, "Monsoon floods")
    look = T.make_data_tools(s)["lookup_location_risk"]
    assert look.invoke({"city": "patna"})["levels"]["Flood"] == "Very High"
    assert "error" in look.invoke({"city": "Atlantis"})


def test_agent_tool_loop():
    used = []
    s = D.build_snapshot(False, "Monsoon floods")
    brief = agents.briefing_text(s, s["cities"][0], "Flood", "English")
    out = "".join(agents.stream_agent(FakeLLM(), agents.AGENT_MAP["response"], brief, [], "plan", None, [], used))
    assert out == "Deploy 3 teams." and used[0]["result"]["rescue_teams"] == 3


def test_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA", tmp_path)
    monkeypatch.setattr(storage, "DB", tmp_path / "t.db")
    storage.add_alert("Patna", "Flood", "Warning", "Flood risk", "English")
    storage.add_report("Patna", "water rising", dict(category="Flooding", urgency="High", credibility="Medium",
                       summary="s", recommended_action="a", needs_verification=True))
    assert storage.get_alerts()[0]["severity"] == "Warning" and storage.get_reports()[0]["urgency"] == "High"
