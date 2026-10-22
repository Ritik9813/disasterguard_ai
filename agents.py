"""Five pipeline agents (one per stage of the DisasterGuard workflow), built with LangChain + Gemini."""
import base64
import json
from dataclasses import dataclass
from typing import Iterator, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

import tools as T
from schemas import AlertPack, DamageAssessment, ReportTriage

BASE_RULES = (
    "You are part of DisasterGuard AI, a decision-support system for disaster risk management in India. "
    "You are NOT an official forecaster: tell people to follow warnings from IMD, NDMA and their State "
    "Disaster Management Authority. Base every claim on the situation briefing and your tool results, "
    "never invent data, and say plainly when data is missing. Use tools for numbers instead of guessing. "
    "Be calm, specific and practical; use short markdown sections. Reply in the language named under "
    "'Reply language' in the briefing."
)


@dataclass(frozen=True)
class Agent:
    key: str
    name: str
    icon: str
    stage_title: str
    short: str
    system: str
    task: str
    tool_names: tuple = ()


AGENTS: list[Agent] = [
    Agent("data", "Data Collection Agent", "🛰️", "Multi-Source Data Collection",
          "Weather, quakes, sensors and reports",
          "You collect and validate data from satellites and weather feeds, earthquake catalogues, "
          "community reports and historical risk maps, and judge its quality.",
          "Produce a data brief for the focus location and hazard: what the data shows (rainfall, wind, "
          "temperature, river rise, earthquakes), which sources it came from, data gaps or quality issues, "
          "and the 5 highest-risk places for this hazard right now.",
          ()),
    Agent("predict", "Risk Prediction Agent", "📈", "AI-Based Risk Prediction",
          "Risk levels, drivers and outlook",
          "You predict disaster risk from the collected data. You explain the drivers behind each risk level "
          "and how confident you are. You can run what-if scenarios with compute_risk_score.",
          "Give the risk assessment for the focus location: risk level and score, the main drivers, a 12 to 48 "
          "hour outlook, confidence, affected areas, and one what-if (for example if rainfall doubled).",
          ("compute_risk_score",)),
    Agent("alert", "Early Warning Agent", "🚨", "Early Warning & Alert System",
          "Alerts for every channel",
          "You write clear public warnings for mobile push, SMS, WhatsApp, sirens and TV or radio. Messages "
          "are short, calm and tell people exactly what to do. Include helpline numbers from emergency_contacts.",
          "Write the warning plan: severity level, who to alert first, and the message for each channel (push, "
          "SMS under 160 characters, WhatsApp, siren pattern, TV or radio) with safety instructions.",
          ("emergency_contacts",)),
    Agent("response", "Response Coordinator", "🚁", "Disaster Response & Management",
          "Teams, routes, shelters, drones",
          "You coordinate emergency response: resource allocation, evacuation routes, drone monitoring and "
          "volunteer coordination. Use allocate_resources for quantities.",
          "Create the response plan: resources needed (call allocate_resources with the estimated people at "
          "risk), evacuation priorities and route principles, shelters, drone monitoring tasks, and how to "
          "coordinate volunteers and community help requests.",
          ("allocate_resources", "emergency_contacts")),
    Agent("recovery", "Recovery Planner", "🏗️", "Post-Disaster Recovery",
          "Damage, aid and rebuilding",
          "You plan recovery after a disaster: damage assessment, aid distribution, rebuilding with "
          "risk-resilient infrastructure and support for livelihoods, health and education.",
          "Create the recovery plan: how to assess damage (satellite, drone, ground), aid distribution and "
          "tracking, rebuilding priorities, community support, and lessons that improve future preparedness. "
          "Use estimate_relief_needs with clearly stated assumed damage figures.",
          ("estimate_relief_needs",)),
]
AGENT_MAP = {a.key: a for a in AGENTS}


# ------------------------------------------------------------------ helpers
def get_llm(api_key: str, model: str, temperature: float) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=temperature)


def briefing_text(snap: dict, city: dict, hazard: str, language: str) -> str:
    keys = ("rain_today", "rain_prev3d", "rain_next2d", "wind_max", "temp_max", "river_rise")
    top = sorted(snap["cities"], key=lambda c: -c["scores"][hazard])[:5]
    strongest = max(snap["quakes"], key=lambda q: q["mag"], default=None)
    lines = [
        f"Reply language: {language}",
        f"Data source: {snap['scenario']} ({snap['source']}), generated {snap['generated']}",
        f"Focus location: {city['name']}, {city['state']} (approx. population {city['pop_lakh']} lakh)",
        f"Hazard of interest: {hazard}",
        "Focus conditions (mm rain, km/h wind, deg C, river rise ratio): "
        + ", ".join(f"{k}={city[k]}" for k in keys),
        "Focus risk scores: " + ", ".join(f"{h}={s} ({city['levels'][h]})" for h, s in city["scores"].items()),
        f"Highest-risk places for {hazard}: "
        + "; ".join(f"{c['name']} ({c['state']}) {c['scores'][hazard]} {c['levels'][hazard]}" for c in top),
        f"Earthquakes in the feed: {len(snap['quakes'])}"
        + (f", strongest M{strongest['mag']} at {strongest['place']}" if strongest else ""),
    ]
    return "\n".join(lines)


def stage_question(agent: Agent, previous: dict) -> str:
    ctx = "\n\n".join(f"## Output of {AGENT_MAP[k].name}\n{v['text'][:3000]}" for k, v in previous.items())
    return agent.task + (f"\n\nEarlier pipeline stages:\n{ctx}" if ctx else "")


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c if isinstance(c, str) else c.get("text", "") for c in content
                       if isinstance(c, str) or c.get("type") == "text")
    return ""


def _human(question: str, images=None) -> HumanMessage:
    if not images:
        return HumanMessage(question)
    parts = [{"type": "text", "text": question}]
    for mime, data in images:
        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}})
    return HumanMessage(parts)


def to_messages(history):
    return [HumanMessage(c) if r == "user" else AIMessage(c) for r, c in history]


def _system(agent: Agent, briefing: str) -> SystemMessage:
    return SystemMessage(f"{BASE_RULES}\n\n{agent.system}\n\nSituation briefing:\n{briefing}")


# ------------------------------------------------------------------ agent loop
def stream_agent(llm, agent: Agent, briefing: str, history, question: str, images=None,
                 extra_tools=(), used: Optional[list] = None, max_steps: int = 5) -> Iterator[str]:
    """Stream an answer, running tool calls between model turns (recorded in `used`)."""
    tool_map = {t.name: t for t in [*(T.STATIC[n] for n in agent.tool_names), *extra_tools]}
    model = llm.bind_tools(list(tool_map.values())) if tool_map else llm
    messages = [_system(agent, briefing), *to_messages(history), _human(question, images)]
    for _ in range(max_steps):
        full = None
        for chunk in model.stream(messages):
            full = chunk if full is None else full + chunk
            piece = _text(chunk.content)
            if piece:
                yield piece
        if full is None or not getattr(full, "tool_calls", None):
            return
        messages.append(full)
        for call in full.tool_calls:
            try:
                result = tool_map[call["name"]].invoke(call["args"])
            except Exception as e:
                result = {"error": str(e)}
            if used is not None:
                used.append({"tool": call["name"], "args": call["args"], "result": result})
            messages.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=call["id"]))
    yield "\n\n_(Stopped after the maximum number of tool steps.)_"


# ------------------------------------------------------------------ structured outputs
def generate_alert_pack(llm, briefing: str, city: str, hazard: str, language: str) -> dict:
    msgs = [_system(AGENT_MAP["alert"], briefing),
            HumanMessage(f"Create the public alert pack for {city} about {hazard}. Write every text field in "
                         f"{language}. Match severity and risk level to the briefing scores. SMS must be "
                         "160 characters or fewer.")]
    return llm.with_structured_output(AlertPack).invoke(msgs).model_dump()


def assess_damage(llm, image: tuple, note: str = "") -> dict:
    system = SystemMessage(BASE_RULES + " You assess disaster damage from photos (ground, drone or satellite). "
                           "Describe only what is visible and state limits honestly.")
    msg = _human("Assess the disaster damage in this image." + (f" Context from the reporter: {note}" if note else ""),
                 [image])
    return llm.with_structured_output(DamageAssessment).invoke([system, msg]).model_dump()


def triage_report(llm, city: str, text: str) -> dict:
    system = SystemMessage(BASE_RULES + " You triage crowdsourced community reports. Treat them as unverified: "
                           "rate credibility from detail and consistency, and flag what needs verification.")
    msg = HumanMessage(f"Location: {city}\nReport: {text}")
    return llm.with_structured_output(ReportTriage).invoke([system, msg]).model_dump()
