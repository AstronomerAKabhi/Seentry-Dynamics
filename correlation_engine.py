"""
Multi-Event Sequence Correlation Engine
Detects attack chains by analyzing sliding event windows per user.
"""
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import NamedTuple

WINDOW_SECONDS = 60   # correlation window



class AttackChain(NamedTuple):
    pattern: str
    severity: str     # LOW / MEDIUM / HIGH / CRITICAL
    description: str
    risk_bonus: int
    events: list


# ── Pattern Definitions ───────────────────────────────────────────────────────

PATTERNS = [
    {
        "id": "RAPID_MASS_DELETE",
        "label": "Mass Delete",
        "severity": "CRITICAL",
        "description": "10+ files deleted within 60 seconds — possible ransomware or wiper.",
        "risk_bonus": 30,
        "check": lambda evts: sum(1 for e in evts if e["type"] == "DELETED") >= 10,
    },
    {
        "id": "CANARY_PLUS_MODIFY",
        "label": "Canary + Mass Modify",
        "severity": "CRITICAL",
        "description": "Canary file triggered alongside mass modifications — active intrusion.",
        "risk_bonus": 40,
        "check": lambda evts: (
            any("canary" in e["path"].lower() for e in evts) and
            sum(1 for e in evts if e["type"] == "MODIFIED") >= 5
        ),
    },
    {
        "id": "RAPID_MASS_CREATE",
        "label": "Mass File Creation",
        "severity": "HIGH",
        "description": "15+ new files created in 60 seconds — possible malware dropping payloads.",
        "risk_bonus": 20,
        "check": lambda evts: sum(1 for e in evts if e["type"] == "CREATED") >= 15,
    },
    {
        "id": "PRIV_FILE_EXFIL",
        "label": "Privileged File Access",
        "severity": "HIGH",
        "description": "Access to credentials, keys, or financial data files detected.",
        "risk_bonus": 25,
        "check": lambda evts: any(
            any(kw in e["path"].lower() for kw in
                ["password", "passwd", "creds", ".pem", ".key", "wallet", "salary", "financial", "secret"])
            for e in evts
        ),
    },
    {
        "id": "NIGHT_DELETE_BURST",
        "label": "After-Hours Delete Burst",
        "severity": "HIGH",
        "description": "Multiple deletions occurring after business hours (21:00-06:00).",
        "risk_bonus": 18,
        "check": lambda evts: (
            sum(1 for e in evts if e["type"] == "DELETED" and
                (datetime.fromtimestamp(e["ts"]).hour >= 21 or
                 datetime.fromtimestamp(e["ts"]).hour < 6)) >= 5
        ),
    },
    {
        "id": "EXT_CHANGE_FLOOD",
        "label": "Extension Change Flood",
        "severity": "MEDIUM",
        "description": "Many files modified with extension changes — possible encryption activity.",
        "risk_bonus": 22,
        "check": lambda evts: (
            len(set(e["path"].rsplit(".", 1)[-1] for e in evts if e["type"] == "MODIFIED")) >= 6 and
            sum(1 for e in evts if e["type"] == "MODIFIED") >= 8
        ),
    },
    {
        "id": "CONFIG_TAMPERING",
        "label": "Config File Tampering",
        "severity": "MEDIUM",
        "description": "Multiple config/ini/env files modified in quick succession.",
        "risk_bonus": 12,
        "check": lambda evts: sum(
            1 for e in evts if e["type"] == "MODIFIED" and
            any(e["path"].lower().endswith(ext) for ext in [".cfg", ".ini", ".env", ".conf", ".xml", ".toml", ".json"])
        ) >= 3,
    },
]


class CorrelationEngine:
    """
    Maintains a per-user sliding event window and fires attack chain alerts
    when pattern conditions are met.
    """
    def __init__(self, cooldown: int = 30):
        """cooldown: seconds before same pattern can fire again for same user"""
        self._windows: dict[str, deque] = defaultdict(lambda: deque())
        self._last_fired: dict[str, dict] = defaultdict(dict)  # user -> {pattern_id -> ts}
        self._cooldown = cooldown
        self._detected_chains: list[dict] = []

    def add_event(self, user: str, event_type: str, file_path: str) -> list[dict]:
        """
        Add event to the user's window and immediately check for patterns.
        Returns list of newly triggered attack chains.
        """
        now = time.time()
        self._windows[user].append({
            "ts": now,
            "type": event_type,
            "path": file_path,
            "user": user,
        })
        # Prune old events outside the window
        while self._windows[user] and now - self._windows[user][0]["ts"] > WINDOW_SECONDS:
            self._windows[user].popleft()

        return self._evaluate(user)

    def _evaluate(self, user: str) -> list[dict]:
        """Check all patterns against the user's current event window."""
        now = time.time()
        window = list(self._windows[user])
        triggered = []

        for pattern in PATTERNS:
            pid = pattern["id"]
            last_t = self._last_fired[user].get(pid, 0)
            if now - last_t < self._cooldown:
                continue  # still cooling down
            try:
                if pattern["check"](window):
                    self._last_fired[user][pid] = now
                    chain = {
                        "id": pid,
                        "label": pattern["label"],
                        "severity": pattern["severity"],
                        "description": pattern["description"],
                        "risk_bonus": pattern["risk_bonus"],
                        "user": user,
                        "ts": now,
                        "event_count": len(window),
                    }
                    triggered.append(chain)
                    self._detected_chains.append(chain)
            except Exception as e:
                print(f"[CorrelationEngine] Pattern {pid} check failed: {e}")

        return triggered

    def get_recent_chains(self, limit: int = 20) -> list[dict]:
        return sorted(self._detected_chains[-limit:], key=lambda x: -x["ts"])

    def get_window_size(self, user: str) -> int:
        return len(self._windows.get(user, []))
