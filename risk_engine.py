"""
Multi-Stage Risk Escalation Engine
Maintains cumulative per-user risk scores with decay, stage thresholds,
and explainable factor tracking.
"""
import time
import threading
from typing import Optional
from collections import defaultdict


# ── Stage definitions ────────────────────────────────────────────────────────
STAGES: list = [
    {"name": "NORMAL",    "min": 0,  "max": 25,  "color": "#10b981", "icon": "OK"},
    {"name": "ELEVATED",  "min": 26, "max": 50,  "color": "#f59e0b", "icon": "!!"},
    {"name": "HIGH",      "min": 51, "max": 75,  "color": "#f97316", "icon": "!!"},
    {"name": "CRITICAL",  "min": 76, "max": 100, "color": "#ef4444", "icon": "!!"},
]

# Base risk deltas
BASE_RISK = {
    "CREATED":  1,
    "MODIFIED": 2,
    "DELETED":  4,
}

ANOMALY_MULTIPLIER   = 2.5
CANARY_FLAT_BONUS    = 50
NIGHT_BONUS          = 3      # per event after 21:00 or before 06:00
DECAY_PER_TICK       = 0.5    # points subtracted every decay tick
DECAY_TICK_SECONDS   = 5      # how often decay runs


def _get_stage(score: float) -> dict:
    for stage in reversed(STAGES):  # type: ignore[arg-type]
        if score >= float(stage["min"]):
            return stage  # type: ignore[return-value]
    return STAGES[0]  # type: ignore[return-value]


class UserRisk:
    """Mutable risk state for one user."""
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.score: float = 0.0
        self.stage: dict = STAGES[0]  # type: ignore[assignment]
        self.last_updated: float = time.time()
        self.explanation: list = []   # recent factor deltas
        self.history: list = []        # full score history (ts, score, stage)

    def apply_delta(self, delta: float, factors: list):
        self.score = max(0.0, min(100.0, self.score + delta))
        self.stage = _get_stage(self.score)
        self.explanation = factors[-10:]  # type: ignore[index]  # keep last 10 factors
        self.last_updated = time.time()
        self.history.append({
            "ts": self.last_updated,
            "score": float(round(float(self.score), 2)),  # type: ignore[call-overload]
            "stage": str(self.stage.get("name", "NORMAL")),
        })
        if len(self.history) > 200:
            self.history = self.history[-200:]  # type: ignore[assignment]

    def decay(self):
        if self.score > 0:
            self.score = max(0.0, self.score - DECAY_PER_TICK)
            self.stage = _get_stage(self.score)
            self.last_updated = time.time()

    def to_dict(self) -> dict:
        return {
            "user": self.user_id,
            "score": float(round(float(self.score), 1)),  # type: ignore[call-overload]
            "stage": str(self.stage.get("name", "NORMAL")),
            "stage_color": str(self.stage.get("color", "#10b981")),
            "stage_icon": str(self.stage.get("icon", "OK")),
            "explanation": self.explanation,
            "last_updated": self.last_updated,
            "history_recent": self.history[-20:],  # type: ignore[misc]
        }


class RiskEngine:
    """
    Master risk engine — processes events, applies scores, runs decay loop.
    """
    def __init__(self):
        self._risks: dict[str, UserRisk] = {}
        self._lock = threading.Lock()
        self._alerts: list[dict] = []
        self._decay_thread = threading.Thread(target=self._decay_loop, daemon=True)
        self._decay_thread.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def process_event(
        self,
        user: str,
        event_type: str,
        file_path: str,
        is_anomaly: bool = False,
        is_canary: bool = False,
        is_night: bool = False,
        chains: Optional[list] = None,
        deviation_score: float = 0.0,
    ) -> dict:
        """
        Compute and apply risk delta for a single event.
        Returns the explanation dict for broadcasting.
        """
        chains = chains or []
        factors = []
        delta = 0.0

        # 1. Base event risk
        base = BASE_RISK.get(event_type, 1)
        factors.append({"name": f"Base ({event_type})", "delta": base})
        delta += base

        # 2. Anomaly multiplier
        if is_anomaly:
            bonus = round(float(base) * (ANOMALY_MULTIPLIER - 1), 2)  # type: ignore[call-overload]
            factors.append({"name": "ML Anomaly Flag", "delta": bonus})
            delta += bonus

        # 3. Canary triggered
        if is_canary:
            factors.append({"name": "Canary Triggered!", "delta": CANARY_FLAT_BONUS})
            delta += CANARY_FLAT_BONUS

        # 4. Night-time activity
        if is_night:
            factors.append({"name": "Night-time Activity", "delta": NIGHT_BONUS})
            delta += NIGHT_BONUS

        # 5. Behavioral deviation
        if deviation_score > 0.3:
            dev_bonus = round(float(deviation_score) * 8, 2)  # type: ignore[call-overload]
            factors.append({"name": f"Behavioral Deviation ({deviation_score:.2f})", "delta": dev_bonus})
            delta += dev_bonus

        # 6. Correlation chains
        for chain in chains:
            bonus = chain.get("risk_bonus", 0)
            factors.append({"name": f"Attack Chain: {chain.get('label','?')}", "delta": bonus})
            delta += bonus

        # Round delta
        delta = round(float(delta), 2)  # type: ignore[call-overload]

        with self._lock:
            if user not in self._risks:
                self._risks[user] = UserRisk(user)
            risk = self._risks[user]
            old_stage = str(risk.stage.get("name", "NORMAL"))
            risk.apply_delta(delta, factors)
            new_stage = str(risk.stage.get("name", "NORMAL"))

        # Fire escalation alert on stage transition
        if new_stage != old_stage and new_stage != "NORMAL":
            self._create_alert(user, new_stage, file_path, factors)

        return {
            "user": user,
            "delta": delta,
            "factors": factors,
            "new_score": risk.score,
            "stage": risk.stage["name"],
        }

    def manual_delta(self, user: str, delta: float, reason: str = "Manual adjustment"):
        """Apply a manual score adjustment (SOC action)."""
        with self._lock:
            if user not in self._risks:
                self._risks[user] = UserRisk(user)
            self._risks[user].apply_delta(delta, [{"name": reason, "delta": delta}])

    def get_risk(self, user: str) -> dict:
        with self._lock:
            if user not in self._risks:
                return {"user": user, "score": 0, "stage": "NORMAL", "stage_color": "#10b981"}
            return self._risks[user].to_dict()

    def get_all_risks(self) -> list[dict]:
        with self._lock:
            return [r.to_dict() for r in self._risks.values()]

    def get_alerts(self, limit: int = 50) -> list:
        return sorted(self._alerts[-limit:], key=lambda a: -a["ts"])  # type: ignore[arg-type]

    def acknowledge_alert(self, alert_id: str, action: str = "acknowledge"):
        for alert in self._alerts:
            if alert["id"] == alert_id:
                alert["status"] = action
                alert["resolved_at"] = time.time()
                if action == "quarantine":
                    # Immediately zero risk for that user
                    self.manual_delta(str(alert["user"]), -100, "SOC Quarantine action")
                elif action == "dismiss":
                    self.manual_delta(str(alert["user"]), -20, "SOC Dismiss action")
                break

    # ── Internals ─────────────────────────────────────────────────────────────

    def _create_alert(self, user: str, stage: str, file_path: str, factors: list):
        import uuid
        stage_info: dict = next((s for s in STAGES if s["name"] == stage), STAGES[0])  # type: ignore[misc]
        icon = str(stage_info.get("icon", "!!"))
        color = str(stage_info.get("color", "#ef4444"))
        alert = {
            "id": str(uuid.uuid4()).replace("-", "")[:8],  # type: ignore[index]
            "user": user,
            "stage": stage,
            "color": color,
            "icon": icon,
            "title": f"{icon} {stage} Alert — {user}",
            "file": file_path,
            "factors": factors,
            "ts": time.time(),
            "status": "open",
        }
        self._alerts.append(alert)
        if len(self._alerts) > 500:
            self._alerts = self._alerts[-500:]  # type: ignore[assignment]

    def _decay_loop(self):
        while True:
            time.sleep(DECAY_TICK_SECONDS)
            with self._lock:
                for risk in self._risks.values():
                    risk.decay()
