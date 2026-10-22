"""DisasterGuard AI - multi-agent disaster risk and early warning prototype. Run: streamlit run app.py"""
import html
import os
from datetime import date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import data as D
import storage
import tools as T
from agents import (AGENT_MAP, AGENTS, assess_damage, briefing_text, generate_alert_pack, get_llm,
                    stage_question, stream_agent, triage_report)
from styles import CSS, STAGE_CSS

load_dotenv()
_ver = tuple(int(p) for p in st.__version__.split(".")[:2] if p.isdigit())
STRETCH = {"width": "stretch"} if _ver >= (1, 50) else {"use_container_width": True}

st.set_page_config(page_title="DisasterGuard AI", page_icon="🛡️", layout="wide")
st.markdown(CSS + STAGE_CSS, unsafe_allow_html=True)

LANGS = ["English", "Hindi", "Punjabi", "Bengali", "Tamil", "Telugu", "Marathi", "Gujarati", "Odia", "Assamese", "Urdu"]
MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
IMG_TYPES = ["png", "jpg", "jpeg", "webp"]
LV = {"Very High": "vh", "High": "h", "Moderate": "m", "Low": "l"}
HZ_ICON = {"Flood": "🌊", "Cyclone": "🌀", "Landslide": "⛰️", "Earthquake": "🫨", "Forest Fire": "🔥", "Heatwave": "🌡️"}
esc = html.escape


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.subheader("Connection")
    api_key = st.text_input("Google API key", value=os.getenv("GOOGLE_API_KEY", ""), type="password",
                            help="Free key: https://aistudio.google.com/apikey")
    model = st.selectbox("Gemini model", MODELS)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.3, 0.05)

    st.subheader("Situation")
    mode = st.radio("Data source", ["Demo scenario", "Live data"], horizontal=True,
                    help="Live uses Open-Meteo (weather, river flow) and USGS (earthquakes). Demo works offline.")
    scenario = st.selectbox("Demo scenario", list(D.SCENARIOS), index=1, disabled=mode == "Live data")
    labels = [f'{c["name"]}, {c["state"]}' for c in D.LOCATIONS]
    focus_label = st.selectbox("Focus location", labels, index=labels.index("Patna, Bihar"))
    hazard = st.selectbox("Hazard", D.HAZARDS)
    language = st.selectbox("Alert and reply language", LANGS)
    if st.button("Refresh data", **STRETCH):
        st.cache_data.clear()
    st.caption("Decision-support prototype. Always follow official warnings from IMD, NDMA and your State "
               "Disaster Management Authority.")


@st.cache_data(ttl=600, show_spinner="Collecting data from all sources...")
def get_snapshot(live: bool, scenario: str, day: str) -> dict:
    return D.build_snapshot(live, scenario)


live = mode == "Live data"
snap = get_snapshot(live, "live" if live else scenario, str(date.today()))
if live and snap["source"] != "live":
    snap = get_snapshot(False, "Normal day", str(date.today()))  # offline fallback keeps the note
city = next(c for c in snap["cities"] if f'{c["name"]}, {c["state"]}' == focus_label)
briefing = briefing_text(snap, city, hazard, language)
S = st.session_state
pipeline = S.get("pipeline")

rows = [{"City": c["name"], "State": c["state"], "lat": c["lat"], "lon": c["lon"], "Score": round(c["scores"][hazard]),
         "Level": c["levels"][hazard], "color": D.LEVEL_COLOR[c["levels"][hazard]],
         "size": 30000 + c["scores"][hazard] * 1800, "Rain today (mm)": c["rain_today"],
         "Rain next 2d (mm)": c["rain_next2d"], "Wind (km/h)": c["wind_max"], "Max temp (C)": c["temp_max"]}
        for c in snap["cities"]]
df = pd.DataFrame(rows)


def extra(key):
    return T.dynamic_tools(snap, key)


def banner(a):
    st.markdown(f'<div class="rh c-{a.key}"><span class="ic">{a.icon}</span><div><b>{a.name}</b>'
                f"<small>{a.stage_title}</small></div></div>", unsafe_allow_html=True)


def show_tools(used):
    if used:
        with st.expander(f"Tools used ({len(used)})"):
            for u in used:
                st.markdown(f'<span class="tool">{u["tool"]}</span>', unsafe_allow_html=True)
                st.json({"input": u["args"], "output": u["result"]}, expanded=False)


# ------------------------------------------------------------------ hero + pipeline strip
src = f'{snap["scenario"]}' + (" (live)" if snap["source"] == "live" else "")
st.markdown(f"""<div class="hero"><div><h1>Disaster<span>Guard</span> AI</h1>
<div class="sub">AI-Powered Disaster Risk Management &amp; Early Warning System</div>
<div class="tag">Predict • Prepare • Protect • Respond • Recover</div>
<div class="chips"><span class="chip">📍 {esc(focus_label)}</span><span class="chip">{HZ_ICON[hazard]} {hazard}</span>
<span class="chip">🗂 {esc(src)}</span><span class="chip">🕒 {snap["generated"]}</span></div></div>
<div class="badge">Safer Communities<br>Resilient India</div></div>""", unsafe_allow_html=True)

steps = "".join(
    f'<div class="step c-{a.key} {"done" if pipeline else ""}"><div class="hd">{i}. {a.stage_title}</div>'
    f'<div class="bd"><span class="ic">{a.icon}</span><b>{a.name}</b>{a.short}<br>'
    f'<span class="st">{"Complete" if pipeline else "Ready"}</span></div></div>'
    for i, a in enumerate(AGENTS, 1))
st.markdown(f'<div class="pipe">{steps}</div>', unsafe_allow_html=True)
if snap["note"]:
    st.warning(snap["note"])

if not api_key:
    st.info("The dashboard works without a key. Add your Google API key in the sidebar to use the AI agents.")
llm = get_llm(api_key, model, temperature) if api_key else None


def need_key() -> bool:
    if llm is None:
        st.info("Add your Google API key in the sidebar to use this feature.")
        return True
    return False


tabs = st.tabs(["Dashboard", "AI pipeline", "Alert studio", "Damage & reports", "Ask the agents", "Architecture"])

# ------------------------------------------------------------------ 1. dashboard
with tabs[0]:
    high = df[df["Level"].isin(["High", "Very High"])]
    people = D.people_at_risk(snap, hazard)
    teams = T.allocate_resources.invoke({"people_at_risk": people, "hazard": hazard})["rescue_teams"]
    st.markdown(f"""<div class="mrow"><div class="mcard m-red"><b>{len(high)}</b><span>Active alerts ({hazard.lower()})</span></div>
<div class="mcard m-blue"><b>{teams}</b><span>Rescue teams needed (estimate)</span></div>
<div class="mcard m-green"><b>{people:,}</b><span>People in high-risk areas (estimate)</span></div></div>""",
                unsafe_allow_html=True)
    left, right = st.columns([3, 2])
    with left:
        st.markdown('<div class="legend">' + "".join(
            f'<span class="lv-{LV[l]}"><i></i>{l}</span>' for l in ["Very High", "High", "Moderate", "Low"])
            + "</div>", unsafe_allow_html=True)
        st.map(df, latitude="lat", longitude="lon", color="color", size="size")
    with right:
        st.markdown(f"**Live alerts: {hazard}**")
        top = df[df["Level"] != "Low"].sort_values("Score", ascending=False).head(6)
        if top.empty:
            st.success(f"No elevated {hazard.lower()} risk in the monitored cities.")
        for r in top.itertuples():
            kind = "Warning" if r.Level in ("High", "Very High") else "Watch"
            st.markdown(f'<div class="al lv-{LV[r.Level]}"><div class="ai">{HZ_ICON[hazard]}</div><div class="at">'
                        f"<b>{hazard} {kind}</b><small>{esc(r.City)}, {esc(r.State)}</small></div>"
                        f'<div class="av">{r.Level}<br><small>score {r.Score}</small></div></div>',
                        unsafe_allow_html=True)
    with st.expander("All monitored locations and conditions"):
        st.dataframe(df.drop(columns=["lat", "lon", "color", "size"]).sort_values("Score", ascending=False),
                     hide_index=True, **STRETCH)
        st.caption("Scores come from a transparent rule-based risk engine (rainfall, river rise, wind, "
                   "temperature, earthquake data and area exposure), not a trained ML model.")

# ------------------------------------------------------------------ 2. pipeline
with tabs[1]:
    st.caption("The five agents run one after another. Each stage reads the briefing and the earlier stages' output.")
    if need_key():
        pass
    elif st.button(f"Run the 5-agent pipeline for {city['name']}", type="primary", **STRETCH):
        out = {}
        try:
            for a in AGENTS:
                banner(a)
                used = []
                text = st.write_stream(stream_agent(llm, a, briefing, [], stage_question(a, out), None, extra(a.key), used))
                out[a.key] = {"text": text, "used": used}
                show_tools(used)
            S.pipeline = out
            st.rerun()
        except Exception as e:
            S.pipeline = out or None
            st.error(f"The pipeline stopped: {e}. Check your API key and model, then try again.")
    if pipeline:
        for t, a in zip(st.tabs([f"{i}. {a.name}" for i, a in enumerate(AGENTS, 1)]), AGENTS):
            with t:
                banner(a)
                st.markdown(pipeline[a.key]["text"])
                show_tools(pipeline[a.key]["used"])
        report = f"# DisasterGuard AI report: {focus_label} ({hazard})\n\n_{src}, {snap['generated']}_\n\n"
        report += "".join(f"## {i}. {a.name}\n\n{pipeline[a.key]['text']}\n\n---\n\n"
                          for i, a in enumerate(AGENTS, 1) if a.key in pipeline)
        st.download_button("Download full report (.md)", report, file_name="disasterguard_report.md", **STRETCH)

# ------------------------------------------------------------------ 3. alert studio
with tabs[2]:
    st.caption(f"Generate a multi-channel public alert for {focus_label} in {language}.")
    if not need_key() and st.button("Generate alert pack", type="primary", **STRETCH):
        with st.spinner("Early Warning Agent is writing..."):
            try:
                S.alert = generate_alert_pack(llm, briefing, focus_label, hazard, language)
                S.alert_meta = (city["name"], hazard, language)
            except Exception as e:
                st.error(f"Could not create the alert: {e}. Try again or switch model.")
    p = S.get("alert")
    if p:
        c1, c2 = st.columns([2, 3])
        steps_html = "".join(f"<li>{esc(s)}</li>" for s in p["safety_instructions"])
        c1.markdown(f'<div class="phone"><div class="ph"><div class="pa">⚠ ALERT · {esc(p["severity"].upper())}</div>'
                    f'<div class="pt">{esc(p["headline"])}</div></div><div class="pb">'
                    f'<p>📍 <b>Your area:</b> {esc(p["area"])}</p><p>🌧 <b>Expected:</b> {esc(p["expected"])}</p>'
                    f'<p class="pr lv-{LV[p["risk_level"]]}">Risk: <b>{esc(p["risk_level"])}</b></p>'
                    f"<b>Safety instructions</b><ul>{steps_html}</ul></div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown("**📱 Push notification**")
            st.code(p["push_notification"], language=None)
            st.markdown(f"**💬 SMS** ({len(p['sms'])}/160 characters)")
            st.code(p["sms"], language=None)
            if len(p["sms"]) > 160:
                st.warning("This SMS is over 160 characters and would be split into two messages.")
            st.markdown("**🟢 WhatsApp**")
            st.code(p["whatsapp"], language=None)
            st.markdown("**🔔 Siren**")
            st.write(p["siren_pattern"])
            st.markdown("**📺 TV / Radio script**")
            st.code(p["tv_radio_script"], language=None)
        if st.button("Publish to alert log"):
            storage.add_alert(focus_label, hazard, p["severity"], p["headline"], language)
            st.toast("Saved to the alert log (nothing is actually sent in this prototype)")
    log = storage.get_alerts(8)
    if log:
        st.markdown("**Alert log**")
        st.dataframe(pd.DataFrame(log).drop(columns=["id"]), hide_index=True, **STRETCH)

# ------------------------------------------------------------------ 4. damage & reports
with tabs[3]:
    a, b = st.columns(2)
    with a:
        st.markdown("#### 📸 Damage assessment from a photo")
        st.caption("Upload a ground, drone or satellite image.")
        photo = st.file_uploader("Image", type=IMG_TYPES, key="dmg_img", label_visibility="collapsed")
        note = st.text_input("Context (optional)", key="dmg_note")
        if photo:
            st.image(photo, width=320)
        if st.button("Assess damage", type="primary", **STRETCH) and photo and not need_key():
            with st.spinner("Analysing the image..."):
                try:
                    S.damage = assess_damage(llm, (photo.type, photo.getvalue()), note)
                except Exception as e:
                    st.error(f"Could not assess the image: {e}")
        d = S.get("damage")
        if d:
            st.metric("Damage level", d["damage_level"], f"confidence: {d['confidence']}")
            st.markdown(f"**Scene:** {d['scene_type']}")
            st.markdown("**Hazards visible:** " + ", ".join(d["hazards_visible"] or ["none noted"]))
            st.markdown("**Infrastructure impacted:** " + ", ".join(d["infrastructure_impacted"] or ["none noted"]))
            st.markdown("**People or assets at risk:** " + d["people_or_assets_at_risk"])
            st.markdown("**Immediate actions**\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(d["immediate_actions"], 1)))
            st.caption("Limits: " + d["limitations"])
    with b:
        st.markdown("#### 💬 Community reports")
        st.caption("Crowdsourced ground information, triaged by AI. Reports stay unverified until confirmed.")
        with st.form("report_form", clear_on_submit=True):
            rcity = st.selectbox("Location", labels, index=labels.index(focus_label))
            rtext = st.text_area("What is happening?", placeholder="Water has entered ground-floor homes near the bus stand...")
            sent = st.form_submit_button("Submit report", type="primary")
        if sent and rtext.strip() and not need_key():
            with st.spinner("Triaging report..."):
                try:
                    storage.add_report(rcity, rtext.strip(), triage_report(llm, rcity, rtext.strip()))
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not triage the report: {e}")
        for r in storage.get_reports(6):
            ulv = {"Critical": "vh", "High": "h", "Medium": "m", "Low": "l"}[r["urgency"]]
            with st.container(border=True):
                st.markdown(f'<span class="pill lv-{ulv}">{r["urgency"]}</span><span class="pill lv-m">{esc(r["category"])}</span>'
                            f'<small>{esc(r["city"])} · {r["ts"]}</small>', unsafe_allow_html=True)
                st.write(r["summary"])
                st.caption(f"Action: {r['action']} · credibility {r['credibility']}"
                           + (" · needs verification" if r["verify"] else ""))

# ------------------------------------------------------------------ 5. chat
with tabs[4]:
    key = st.radio("Agent", [a.key for a in AGENTS], horizontal=True, label_visibility="collapsed",
                   format_func=lambda k: f"{AGENT_MAP[k].icon} {AGENT_MAP[k].name}")
    agent = AGENT_MAP[key]
    chats = S.setdefault("chats", {})
    history = chats.setdefault(key, [])
    banner(agent)
    if history and st.button("Clear this chat"):
        chats[key] = []
        st.rerun()
    if not history:
        st.caption(f"Ask the {agent.name} anything about {focus_label}. You can attach a photo.")
    for role, text in history:
        with st.chat_message(role, avatar=agent.icon if role == "assistant" else None):
            st.markdown(text)
    msg = st.chat_input(f"Message the {agent.name}", accept_file=True, file_type=IMG_TYPES)
    if msg and not need_key():
        text = msg.text or "Please look at the attached photo."
        images = [(f.type, f.getvalue()) for f in msg.files]
        with st.chat_message("user"):
            st.markdown(text)
        with st.chat_message("assistant", avatar=agent.icon):
            used = []
            try:
                answer = st.write_stream(stream_agent(llm, agent, briefing, history, text, images, extra(key), used))
                history += [("user", text + (" [photo attached]" if images else "")), ("assistant", answer)]
                show_tools(used)
            except Exception as e:
                st.error(f"No reply: {e}. Check your API key and try again.")

# ------------------------------------------------------------------ 6. architecture
with tabs[5]:
    st.markdown("#### System architecture")
    st.graphviz_chart(r"""digraph G {
 rankdir=LR; bgcolor="transparent"; nodesep=0.25;
 node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11 fillcolor="#ffffff" color="#9db4d8"];
 edge [color="#0B2A5B"];
 subgraph cluster_src { label="Data sources"; style="rounded"; color="#1F4E9A";
  w [label="Weather & rainfall\n(Open-Meteo)"]; r [label="River flow\n(Open-Meteo flood)"]; q [label="Earthquakes\n(USGS)"];
  c [label="Community reports\n+ photos"]; dm [label="Demo scenarios\n(offline)"]; }
 subgraph cluster_ai { label="AI & analytics engine"; style="rounded"; color="#1E7B45";
  p [label="Data processing\n(snapshot)"]; e [label="Risk engine\n(rule-based scores)"]; g [label="Gemini agents\n(LangChain, tools)"]; }
 subgraph cluster_out { label="Outputs & services"; style="rounded"; color="#F26B1D";
  a1 [label="Early warning alerts"]; a2 [label="Risk map & dashboard"]; a3 [label="Response coordination"];
  a4 [label="Resource management"]; a5 [label="Recovery planning"]; }
 w->p; r->p; q->p; c->p; dm->p; p->e->g; g->a1; g->a2; g->a3; g->a4; g->a5;
 cloud [label="Cloud infrastructure\n(Streamlit, SQLite, Docker)" fillcolor="#E6EEFA"]; g->cloud [dir=both style=dashed];
}""")
    x, y = st.columns(2)
    with x:
        st.markdown("#### Impact")
        st.markdown("- Saves lives through early warnings\n- Reduces economic damage\n- Faster, more efficient response\n"
                    "- Better use of resources\n- Builds resilient, prepared communities")
        st.markdown("#### Future scope")
        st.markdown("- More accurate AI models trained on big data\n- Integration with smart-city systems\n"
                    "- Global disaster-data collaboration\n- Satellite, drone and IoT at larger scale\n"
                    "- Real-time multilingual alerts\n- Support for climate-change adaptation")
    with y:
        st.markdown("#### What this prototype does and does not do")
        st.dataframe(pd.DataFrame([
            ["IoT sensors, satellites", "Open-Meteo, USGS and demo scenarios stand in for sensor feeds"],
            ["ML & deep-learning prediction", "Transparent rule-based risk engine plus Gemini reasoning"],
            ["SMS, WhatsApp, siren, TV", "Messages are drafted and logged, never actually sent"],
            ["Resource allocation", "Indicative ratios (see the tool assumptions)"],
            ["Drone and satellite damage assessment", "Single-photo analysis with Gemini vision"],
        ], columns=["In the vision", "In this prototype"]), hide_index=True, **STRETCH)

st.markdown('<div class="disc">DisasterGuard AI is a decision-support prototype, not an official forecasting or '
            "warning service. Follow IMD, NDMA and State Disaster Management Authority warnings. "
            "Emergency: 112.</div>", unsafe_allow_html=True)
