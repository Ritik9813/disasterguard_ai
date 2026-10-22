# DisasterGuard AI

AI-powered disaster risk management and early warning prototype for India, built with **LangChain + `langchain-google-genai` (Gemini)** and Streamlit. Five agents map to the five stages: data collection, risk prediction, early warning, response, recovery.

## Run
```bash
pip install -r requirements.txt
cp .env.example .env      # add GOOGLE_API_KEY, or paste it in the sidebar
streamlit run app.py
```
The dashboard works without a key. The AI tabs need a free Gemini key: https://aistudio.google.com/apikey

## Tabs
Dashboard (India risk map, live alerts, estimates) | AI pipeline (5 agents in sequence, streaming, tool calls) |
Alert studio (phone preview, SMS/WhatsApp/siren/TV text in 11 languages) | Damage & reports (photo assessment, community report triage) |
Ask the agents | Architecture.

## Data modes
- **Demo scenario** (offline): Normal day, Monsoon floods, Cyclone landfall, Himalayan landslides, Heatwave, Earthquake.
- **Live data**: Open-Meteo (weather, river flow) and USGS (earthquakes). Falls back to demo if the network fails.

## Honest limits
Risk scores come from a transparent rule-based engine, not a trained ML model. Alerts are drafted and logged, never sent.
Resource and cost numbers are indicative ratios. This is not an official warning service: follow IMD, NDMA and your SDMA.

Tests (offline): `python -m pytest -q tests`
