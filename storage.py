"""SQLite storage for community reports and the alert log."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).parent / "data"
DB = DATA / "disasterguard.db"

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, city TEXT, text TEXT,
       category TEXT, urgency TEXT, credibility TEXT, summary TEXT, action TEXT, verify INTEGER)""",
    """CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, city TEXT, hazard TEXT,
       severity TEXT, headline TEXT, language TEXT)""",
]


def _conn():
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    for s in SCHEMA:
        c.execute(s)
    return c


def _now() -> str:
    return datetime.now().strftime("%d %b %H:%M")


def add_report(city: str, text: str, triage: dict):
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO reports(ts,city,text,category,urgency,credibility,summary,action,verify)"
                  " VALUES(?,?,?,?,?,?,?,?,?)",
                  (_now(), city, text, triage["category"], triage["urgency"], triage["credibility"],
                   triage["summary"], triage["recommended_action"], int(triage["needs_verification"])))


def get_reports(limit: int = 20) -> list:
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,))]


def add_alert(city: str, hazard: str, severity: str, headline: str, language: str):
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO alerts(ts,city,hazard,severity,headline,language) VALUES(?,?,?,?,?,?)",
                  (_now(), city, hazard, severity, headline, language))


def get_alerts(limit: int = 20) -> list:
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))]


def clear_all():
    with closing(_conn()) as c, c:
        c.execute("DELETE FROM reports")
        c.execute("DELETE FROM alerts")
