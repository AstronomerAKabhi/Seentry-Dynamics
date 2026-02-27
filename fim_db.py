"""
FIM SQLite Database Layer
Provides lightweight persistent storage for events, alerts, and risk history.
"""
import sqlite3
import json
import time
import threading
import os
from typing import Optional

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fim_data.db")
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    with _lock, _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL NOT NULL,
                event_type  TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                user        TEXT DEFAULT 'system',
                process     TEXT DEFAULT 'Unknown',
                risk_delta  REAL DEFAULT 0,
                is_anomaly  INTEGER DEFAULT 0,
                stage       TEXT DEFAULT 'NORMAL'
            );

            CREATE TABLE IF NOT EXISTS risk_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       REAL NOT NULL,
                user            TEXT NOT NULL,
                score           REAL NOT NULL,
                stage           TEXT NOT NULL,
                explanation     TEXT
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id          TEXT PRIMARY KEY,
                timestamp   REAL NOT NULL,
                user        TEXT NOT NULL,
                title       TEXT NOT NULL,
                severity    TEXT NOT NULL,
                stage       TEXT NOT NULL,
                file_path   TEXT,
                factors     TEXT,
                status      TEXT DEFAULT 'open',
                resolved_at REAL
            );

            CREATE TABLE IF NOT EXISTS clusters (
                user_id     TEXT PRIMARY KEY,
                cluster_id  INTEGER,
                role_label  TEXT,
                features    TEXT,
                updated_at  REAL
            );

            CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_alerts_ts   ON alerts(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_risk_user   ON risk_log(user, timestamp DESC);
        """)


# ── Events ─────────────────────────────────────────────────────────────────

def store_event(event_type: str, file_path: str, user: str = "system",
                process: str = "Unknown", risk_delta: float = 0,
                is_anomaly: bool = False, stage: str = "NORMAL"):
    with _lock, _get_conn() as conn:
        conn.execute(
            """INSERT INTO events (timestamp, event_type, file_path, user, process, risk_delta, is_anomaly, stage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), event_type, file_path, user, process,
             round(float(risk_delta), 2), int(is_anomaly), stage)  # type: ignore[call-overload]
        )


def get_timeline(limit: int = 100, user: Optional[str] = None) -> list:
    with _lock, _get_conn() as conn:
        if user:
            rows = conn.execute(
                "SELECT * FROM events WHERE user=? ORDER BY timestamp DESC LIMIT ?",
                (user, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_event_count(event_type: Optional[str] = None) -> int:
    with _lock, _get_conn() as conn:
        if event_type:
            return conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?", (event_type,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]


# ── Alerts ──────────────────────────────────────────────────────────────────

def store_alert(alert: dict):
    with _lock, _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO alerts
               (id, timestamp, user, title, severity, stage, file_path, factors, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert["id"],
                alert.get("ts", time.time()),
                alert["user"],
                alert["title"],
                alert.get("stage", "HIGH"),
                alert.get("stage", "HIGH"),
                alert.get("file", ""),
                json.dumps(alert.get("factors", [])),
                alert.get("status", "open"),
            )
        )


def get_alerts(limit: int = 50, status: Optional[str] = None) -> list:
    with _lock, _get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE status=? ORDER BY timestamp DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
    result = []
    for r in rows:
        d: dict = dict(r)
        try:
            parsed = json.loads(d.get("factors") or "[]")
            d["factors"] = parsed if isinstance(parsed, list) else []  # type: ignore[assignment]
        except Exception:
            d["factors"] = []  # type: ignore[assignment]
        result.append(d)
    return result


def update_alert_status(alert_id: str, status: str):
    with _lock, _get_conn() as conn:
        conn.execute(
            "UPDATE alerts SET status=?, resolved_at=? WHERE id=?",
            (status, time.time(), alert_id)
        )


# ── Risk Log ─────────────────────────────────────────────────────────────────

def log_risk(user: str, score: float, stage: str, explanation: list):
    with _lock, _get_conn() as conn:
        conn.execute(
            "INSERT INTO risk_log (timestamp, user, score, stage, explanation) VALUES (?, ?, ?, ?, ?)",
            (time.time(), user, round(float(score), 2), stage, json.dumps(explanation))  # type: ignore[call-overload]
        )


def get_risk_history(user: str, limit: int = 50) -> list:
    with _lock, _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM risk_log WHERE user=? ORDER BY timestamp DESC LIMIT ?",
            (user, limit)
        ).fetchall()
    result = []
    for r in rows:
        d: dict = dict(r)
        try:
            parsed = json.loads(d.get("explanation") or "[]")
            d["explanation"] = parsed if isinstance(parsed, list) else []  # type: ignore[assignment]
        except Exception:
            d["explanation"] = []  # type: ignore[assignment]
        result.append(d)
    return result


# ── Clusters ──────────────────────────────────────────────────────────────────

def upsert_cluster(user_id: str, cluster_id: int, role_label: str, features: list):
    with _lock, _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO clusters (user_id, cluster_id, role_label, features, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, cluster_id, role_label, json.dumps(features), time.time())
        )


def get_clusters() -> list:
    with _lock, _get_conn() as conn:
        rows = conn.execute("SELECT * FROM clusters ORDER BY cluster_id").fetchall()
    result = []
    for r in rows:
        d: dict = dict(r)
        try:
            parsed = json.loads(d.get("features") or "[]")
            d["features"] = parsed if isinstance(parsed, list) else []  # type: ignore[assignment]
        except Exception:
            d["features"] = []  # type: ignore[assignment]
        result.append(d)
    return result


# Initialize on import
init_db()
