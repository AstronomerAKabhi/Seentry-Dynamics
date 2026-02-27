"""
ML Model Layer
- AnomalyDetector: Isolation Forest for per-event anomaly detection
- RoleClusterer: KMeans for role-based user clustering
Auto-retrains every RETRAIN_INTERVAL events.
"""
import threading
from typing import Optional

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

RETRAIN_INTERVAL = 50   # retrain after this many new events
MIN_SAMPLES = 10        # minimum events before training


class AnomalyDetector:
    """
    Wraps sklearn IsolationForest.
    Expects feature vectors: [events_per_hr, night_ratio, ext_diversity, delete_ratio, path_depth]
    """
    def __init__(self, contamination: float = 0.1):
        self._contamination = contamination
        self._model: Optional[object] = None
        self._lock = threading.Lock()
        self._buffer: list = []
        self._event_count = 0
        self._trained = False

    def add_sample(self, features: list):
        with self._lock:
            self._buffer.append(features)
            self._event_count += 1
            if self._event_count % RETRAIN_INTERVAL == 0 and len(self._buffer) >= MIN_SAMPLES:
                self._retrain()

    def is_anomaly(self, features: list) -> tuple:
        """Returns (is_anomaly, anomaly_score -1..0, lower=more anomalous)."""
        with self._lock:
            if not self._trained or self._model is None:
                return False, 0.0
            try:
                X = np.array([features])
                pred = self._model.predict(X)[0]       # -1 = anomaly, 1 = normal
                score = self._model.score_samples(X)[0]  # log-likelihood; lower = more anomalous
                return pred == -1, float(score)
            except Exception:
                return False, 0.0

    def _retrain(self):
        try:
            from sklearn.ensemble import IsolationForest
            if np is None:
                raise ImportError("numpy not available")
            X = np.array(self._buffer[-500:])  # use last 500 samples
            model = IsolationForest(
                n_estimators=100,
                contamination=self._contamination,
                random_state=42
            )
            model.fit(X)
            self._model = model
            self._trained = True
        except Exception as e:
            print(f"[ML] AnomalyDetector retrain failed: {e}")

    @property
    def is_trained(self) -> bool:
        return self._trained


class RoleClusterer:
    """
    KMeans clustering for role-based user grouping.
    Clusters users into K roles based on their behavioral feature vectors.
    """
    K = 4  # SOC Analyst, Admin, Developer, Suspect

    ROLE_LABELS = {
        0: "Standard User",
        1: "Power User",
        2: "Admin / DevOps",
        3: "Suspicious Actor",
    }

    def __init__(self):
        self._model: Optional[object] = None
        self._users: list = []
        self._lock = threading.Lock()
        self._trained = False

    def fit(self, user_features: dict):
        """Train on a dict of {user_id: feature_vector}."""
        if len(user_features) < self.K:
            return  # not enough users yet
        try:
            from sklearn.cluster import KMeans
            users = list(user_features.keys())
            X = np.array(list(user_features.values()))
            model = KMeans(n_clusters=self.K, random_state=42, n_init=10)
            model.fit(X)
            with self._lock:
                self._model = model
                self._users = users
                self._trained = True
        except Exception as e:
            print(f"[ML] RoleClusterer fit failed: {e}")

    def predict(self, features: list) -> tuple:
        """Returns (cluster_id, role_label)."""
        with self._lock:
            if not self._trained or self._model is None:
                return -1, "Unknown"
            try:
                cluster_id = int(self._model.predict(np.array([features]))[0])
                return cluster_id, self.ROLE_LABELS.get(cluster_id, "Unknown")
            except Exception:
                return -1, "Unknown"

    def get_all_assignments(self, user_features: dict) -> list:
        """Returns cluster assignment for each user."""
        results = []
        with self._lock:
            if not self._trained or self._model is None:
                return [{"user": u, "cluster": -1, "role": "Unknown"} for u in user_features]
            try:
                users = list(user_features.keys())
                X = np.array(list(user_features.values()))
                labels = self._model.predict(X)
                centers = self._model.cluster_centers_
                for i, user in enumerate(users):
                    c = int(labels[i])
                    results.append({
                        "user": user,
                        "cluster": c,
                        "role": self.ROLE_LABELS.get(c, "Unknown"),
                        "features": [round(f, 3) for f in user_features[user]],
                        "center_distance": round(
                            float(np.linalg.norm(np.array(user_features[user]) - centers[c])), 3
                        )
                    })
            except Exception:
                pass
        return results

    @property
    def is_trained(self) -> bool:
        return self._trained
