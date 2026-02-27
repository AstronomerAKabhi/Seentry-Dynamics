"""
Behavioral Baseline & Privilege Deviation Engine
Learns per-user file activity patterns and scores deviations.
"""
import time
import math
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional


class UserProfile:
    """Sliding-window behavioral profile for a single user/entity."""
    WINDOW = 200  # max events to keep in memory

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.events: deque = deque(maxlen=self.WINDOW)
        self.path_counts: dict = defaultdict(int)
        self.ext_counts: dict = defaultdict(int)
        self.hour_counts: dict = defaultdict(int)   # {0..23: count}
        self.type_counts: dict = defaultdict(int)   # {CREATED/MODIFIED/DELETED: count}
        self.total_events: int = 0
        self.last_seen: float = time.time()

    def record(self, event_type: str, file_path: str):
        ts = time.time()
        hour = datetime.fromtimestamp(ts).hour
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "none"

        self.events.append({
            "ts": ts,
            "type": event_type,
            "path": file_path,
            "hour": hour,
            "ext": ext,
        })
        self.path_counts[file_path] += 1
        self.ext_counts[ext] += 1
        self.hour_counts[hour] += 1
        self.type_counts[event_type] += 1
        self.total_events += 1
        self.last_seen = ts

    # ── Derived features ─────────────────────────────────────────────────────

    def events_per_hour(self) -> float:
        """Average events per active hour (based on window)."""
        if not self.events:
            return 0.0
        window_secs = max(time.time() - self.events[0]["ts"], 1)
        return len(self.events) / max(window_secs / 3600, 0.001)

    def night_ratio(self) -> float:
        """Fraction of events occurring between 21:00-06:00."""
        total = sum(self.hour_counts.values()) or 1
        night = sum(v for h, v in self.hour_counts.items() if h >= 21 or h < 6)
        return night / total

    def extension_diversity(self) -> float:
        """Entropy of file extension distribution."""
        total = sum(self.ext_counts.values()) or 1
        probs = [c / total for c in self.ext_counts.values()]
        return -sum(p * math.log2(p + 1e-9) for p in probs)

    def delete_ratio(self) -> float:
        total = sum(self.type_counts.values()) or 1
        return self.type_counts.get("DELETED", 0) / total

    def path_depth_avg(self) -> float:
        if not self.events:
            return 0.0
        depths = [e["path"].count("\\") + e["path"].count("/") for e in self.events]
        return sum(depths) / len(depths)

    def feature_vector(self) -> list:
        return [
            self.events_per_hour(),
            self.night_ratio(),
            self.extension_diversity(),
            self.delete_ratio(),
            self.path_depth_avg(),
        ]

    def summary(self) -> dict:
        return {
            "user": self.user_id,
            "total_events": self.total_events,
            "events_per_hour": round(self.events_per_hour(), 2),  # type: ignore[call-overload]
            "night_ratio": round(self.night_ratio(), 3),  # type: ignore[call-overload]
            "ext_diversity": round(self.extension_diversity(), 3),  # type: ignore[call-overload]
            "delete_ratio": round(self.delete_ratio(), 3),  # type: ignore[call-overload]
            "path_depth_avg": round(self.path_depth_avg(), 2),  # type: ignore[call-overload]
            "top_extensions": sorted(self.ext_counts.items(), key=lambda x: -x[1])[:5],  # type: ignore[misc]
            "type_breakdown": dict(self.type_counts),
            "last_seen": self.last_seen,
        }


class BehavioralEngine:
    """
    Central behavioral engine that maintains user profiles and detects deviations.
    """
    # Weights for deviation score
    _WEIGHTS = {
        "delete_surge":   0.35,
        "night_activity": 0.20,
        "ext_diversity":  0.15,
        "burst_rate":     0.20,
        "path_depth":     0.10,
    }

    def __init__(self):
        self._profiles: dict[str, UserProfile] = {}
        # Baseline thresholds (updated dynamically)
        self._baselines: dict[str, dict] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def record_event(self, user: str, file_path: str, event_type: str):
        if user not in self._profiles:
            self._profiles[user] = UserProfile(user)
        self._profiles[user].record(event_type, file_path)
        self._update_baseline(user)

    def get_deviation_score(self, user: str) -> tuple[float, list]:
        """
        Returns (score 0-1, list of factor dicts) for a user.
        Higher = more anomalous vs. their own baseline.
        """
        if user not in self._profiles:
            return 0.0, []
        profile = self._profiles[user]
        baseline = self._baselines.get(user, {})
        return self._compute_deviation(profile, baseline)

    def get_profile(self, user: str) -> dict:
        if user not in self._profiles:
            return {}
        return self._profiles[user].summary()

    def get_all_profiles(self) -> list[dict]:
        return [p.summary() for p in self._profiles.values()]

    def get_feature_vectors(self) -> dict[str, list]:
        return {uid: p.feature_vector() for uid, p in self._profiles.items()}

    def get_hourly_heatmap(self, user: str) -> list[int]:
        """Returns 24-element list of event counts per hour."""
        if user not in self._profiles:
            return [0] * 24
        h = self._profiles[user].hour_counts
        return [h.get(i, 0) for i in range(24)]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _update_baseline(self, user: str):
        """Update rolling baseline from current profile stats."""
        p = self._profiles[user]
        old = self._baselines.get(user, {})
        alpha = 0.05  # EMA smoothing
        self._baselines[user] = {
            "events_per_hour": (1 - alpha) * old.get("events_per_hour", p.events_per_hour()) + alpha * p.events_per_hour(),
            "night_ratio":     (1 - alpha) * old.get("night_ratio", p.night_ratio()) + alpha * p.night_ratio(),
            "ext_diversity":   (1 - alpha) * old.get("ext_diversity", p.extension_diversity()) + alpha * p.extension_diversity(),
            "delete_ratio":    (1 - alpha) * old.get("delete_ratio", p.delete_ratio()) + alpha * p.delete_ratio(),
            "path_depth_avg":  (1 - alpha) * old.get("path_depth_avg", p.path_depth_avg()) + alpha * p.path_depth_avg(),
        }

    def _compute_deviation(self, profile: UserProfile, baseline: dict) -> tuple[float, list]:
        factors = []

        def _delta(current, base, label, weight):
            """Score how much current deviates above baseline."""
            if base == 0:
                return
            ratio = (current - base) / (base + 1e-9)
            component = max(0.0, min(1.0, ratio)) * weight
            if component > 0.01:
                factors.append({"name": label, "value": round(current, 3),  # type: ignore[call-overload]
                                 "baseline": round(base, 3), "contribution": round(component, 3)})

        _delta(profile.delete_ratio(),       baseline.get("delete_ratio", 0),      "Deletion Surge",      self._WEIGHTS["delete_surge"])
        _delta(profile.night_ratio(),        baseline.get("night_ratio", 0),        "Night-time Activity", self._WEIGHTS["night_activity"])
        _delta(profile.extension_diversity(), baseline.get("ext_diversity", 0),    "Extension Diversity", self._WEIGHTS["ext_diversity"])
        _delta(profile.events_per_hour(),    baseline.get("events_per_hour", 0),   "Burst Rate",          self._WEIGHTS["burst_rate"])
        _delta(profile.path_depth_avg(),     baseline.get("path_depth_avg", 0),    "Path Depth Anomaly",  self._WEIGHTS["path_depth"])

        score = sum(f["contribution"] for f in factors)
        return min(score, 1.0), factors  # type: ignore[return-value]
