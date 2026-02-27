"""Smoke test for all new engine modules."""
import sys
sys.path.insert(0, '.')

from behavioral_engine import BehavioralEngine
from correlation_engine import CorrelationEngine
from risk_engine import RiskEngine
import fim_db

# Test behavioral engine
be = BehavioralEngine()
for i in range(20):
    be.record_event('alice', f'C:/test/file_{i}.txt', 'DELETED')
score, factors = be.get_deviation_score('alice')
print(f'[OK] Behavioral deviation score: {score:.3f}, factors: {len(factors)}')

# Test correlation engine
ce = CorrelationEngine()
chains = []
for i in range(15):
    chains += ce.add_event('alice', 'DELETED', f'C:/test/file_{i}.txt')
print(f'[OK] Correlation chains triggered: {len(chains)}')
for c in chains:
    print(f'     - {c["label"]} [{c["severity"]}] +{c["risk_bonus"]}pts')

# Test risk engine
re = RiskEngine()
result = re.process_event(
    user='alice', event_type='DELETED',
    file_path='C:/test/secret.pem',
    is_anomaly=True, is_canary=True,
    chains=chains[:1]
)
print(f'[OK] Risk score: {result["new_score"]:.1f}, stage: {result["stage"]}, delta: {result["delta"]}')
print(f'     Factors: {[f["name"] for f in result["factors"]]}')

# Test DB
fim_db.store_event('DELETED', 'C:/test/secret.pem', user='alice',
                   risk_delta=result['delta'], stage=result['stage'])
timeline = fim_db.get_timeline(limit=5)
print(f'[OK] DB timeline stored, entries: {len(timeline)}')

# Test ML (sklearn)
from ml_model import AnomalyDetector, RoleClusterer
ad = AnomalyDetector()
fv = be.get_feature_vectors().get('alice', [0.0]*5)
ad.add_sample(fv)
print(f'[OK] AnomalyDetector sample added, feature vector: {[round(x,3) for x in fv]}')

print('\n[ALL TESTS PASSED] ✓')
