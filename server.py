"""
FastAPI Server — Behavioral FIM + Risk Engine + Forensic Dashboard
"""
import asyncio
import time
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, WebSocket, Request, HTTPException  # type: ignore[import-untyped]
from fastapi.responses import HTMLResponse, JSONResponse  # type: ignore[import-untyped]
from fastapi.templating import Jinja2Templates  # type: ignore[import-untyped]
import uvicorn  # type: ignore[import-untyped]
import os
import json
import psutil  # type: ignore[import-untyped]

from logger import log_queue  # type: ignore[import-untyped]
from config import DIRECTORIES_TO_WATCH  # type: ignore[import-untyped]
from behavioral_engine import BehavioralEngine  # type: ignore[import-untyped]
from ml_model import AnomalyDetector, RoleClusterer  # type: ignore[import-untyped]
from correlation_engine import CorrelationEngine  # type: ignore[import-untyped]
from risk_engine import RiskEngine  # type: ignore[import-untyped]
import fim_db  # type: ignore[import-untyped]


app = FastAPI(title="Behavioral FIM")

# ── Setup ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Engine singletons
behavioral_engine = BehavioralEngine()
anomaly_detector  = AnomalyDetector(contamination=0.1)
role_clusterer    = RoleClusterer()
correlation_engine = CorrelationEngine()
risk_engine       = RiskEngine()

active_connections: list[WebSocket] = []
log_history: list[str] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_night() -> bool:
    h = datetime.now().hour
    return h >= 21 or h < 6


def get_file_tree() -> dict:
    tree: dict = {"name": "Root", "children": []}
    for directory in DIRECTORIES_TO_WATCH:
        if os.path.exists(directory):
            tree["children"].append(_build_node(directory))  # type: ignore[union-attr]
    return tree


def _build_node(path: str) -> dict:
    node: dict = {"name": os.path.basename(path), "path": path, "type": "folder", "children": []}
    try:
        for entry in os.scandir(path):
            if entry.is_dir():
                node["children"].append(_build_node(entry.path))  # type: ignore[union-attr]
            else:
                node["children"].append({"name": entry.name, "path": entry.path, "type": "file"})  # type: ignore[union-attr]
    except PermissionError:
        pass
    return node


async def _broadcast(message: dict):
    text = json.dumps(message)
    dead = []
    for ws in active_connections:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/risk")
async def get_all_risks():
    return JSONResponse(risk_engine.get_all_risks())


@app.get("/api/risk/{user}")
async def get_user_risk(user: str):
    return JSONResponse(risk_engine.get_risk(user))


@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    return JSONResponse(risk_engine.get_alerts(limit=limit))


@app.post("/api/alerts/{alert_id}/action")
async def soc_action(alert_id: str, request: Request):
    body = await request.json()
    action = body.get("action", "acknowledge")
    risk_engine.acknowledge_alert(alert_id, action)
    fim_db.update_alert_status(alert_id, action)
    await _broadcast({"type": "alert_update", "alert_id": alert_id, "action": action})
    return {"ok": True, "alert_id": alert_id, "action": action}


@app.get("/api/timeline")
async def get_timeline(limit: int = 100, user: Optional[str] = None):
    return JSONResponse(fim_db.get_timeline(limit=limit, user=user))


@app.get("/api/clusters")
async def get_clusters():
    vectors = behavioral_engine.get_feature_vectors()
    if len(vectors) >= role_clusterer.K:
        role_clusterer.fit(vectors)
    assignments = role_clusterer.get_all_assignments(vectors)
    for a in assignments:
        fim_db.upsert_cluster(a["user"], a["cluster"], a["role"], a.get("features", []))
    return JSONResponse(assignments)


@app.get("/api/users")
async def get_users():
    return JSONResponse(behavioral_engine.get_all_profiles())


@app.get("/api/users/{user}/heatmap")
async def get_heatmap(user: str):
    return JSONResponse(behavioral_engine.get_hourly_heatmap(user))


@app.get("/api/stats")
async def get_stats():
    return JSONResponse({
        "total_events": fim_db.get_event_count(),
        "total_created": fim_db.get_event_count("CREATED"),
        "total_modified": fim_db.get_event_count("MODIFIED"),
        "total_deleted": fim_db.get_event_count("DELETED"),
        "active_risks": len(risk_engine.get_all_risks()),
        "open_alerts": len([a for a in risk_engine.get_alerts() if a.get("status") == "open"]),
    })


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    # Send initial tree and history
    try:
        await websocket.send_text(json.dumps({"type": "tree", "data": get_file_tree()}))
    except Exception:
        pass

    for msg in log_history[-30:]:  # type: ignore[misc]
        try:
            await websocket.send_text(msg)
        except Exception:
            pass

    # Send current risk state
    try:
        await websocket.send_text(json.dumps({"type": "risk_snapshot", "data": risk_engine.get_all_risks()}))
        await websocket.send_text(json.dumps({"type": "alerts_snapshot", "data": risk_engine.get_alerts(20)}))
    except Exception:
        pass

    try:
        while True:
            await websocket.receive_text()
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)


# ── Background Tasks ──────────────────────────────────────────────────────────

async def broadcast_logs():
    """Read FIM log queue, run through all engines, broadcast results."""
    while True:
        while not log_queue.empty():
            log_entry = log_queue.get()
            message = json.dumps({"type": "log", "data": log_entry})
            log_history.append(message)
            if len(log_history) > 100:
                log_history.pop(0)

            # Parse event info from log entry
            event_type = "MODIFIED"
            file_path  = "unknown"
            user       = "system"

            if "Event: CREATED" in log_entry:
                event_type = "CREATED"
            elif "Event: DELETED" in log_entry:
                event_type = "DELETED"
            elif "Event: MODIFIED" in log_entry:
                event_type = "MODIFIED"

            try:
                fp_part = log_entry.split("File: ")
                if len(fp_part) > 1:
                    file_path = fp_part[1].split(" |")[0].strip()
            except Exception:
                pass

            is_canary = "CANARY" in log_entry.upper()

            # Skip heartbeat-only messages for engine processing
            if "HEARTBEAT" not in log_entry:
                # 1. Behavioral engine
                behavioral_engine.record_event(user, file_path, event_type)
                dev_score, _ = behavioral_engine.get_deviation_score(user)

                # 2. ML anomaly check
                fv = behavioral_engine.get_feature_vectors().get(user, [0] * 5)
                anomaly_detector.add_sample(fv)
                is_anomaly, _ = anomaly_detector.is_anomaly(fv)

                # 3. Correlation engine
                chains = correlation_engine.add_event(user, event_type, file_path)

                # 4. Risk engine
                risk_result = risk_engine.process_event(
                    user=user,
                    event_type=event_type,
                    file_path=file_path,
                    is_anomaly=is_anomaly,
                    is_canary=is_canary,
                    is_night=_is_night(),
                    chains=chains,
                    deviation_score=dev_score,
                )

                # 5. Persist to DB
                fim_db.store_event(
                    event_type=event_type,
                    file_path=file_path,
                    user=user,
                    risk_delta=risk_result["delta"],
                    is_anomaly=is_anomaly,
                    stage=risk_result["stage"],
                )

                # For new alerts, persist them too
                for alert in risk_engine.get_alerts(1):
                    if alert.get("status") == "open" and time.time() - alert.get("ts", 0) < 3:
                        fim_db.store_alert(alert)

                # Broadcast enriched event
                await _broadcast({
                    "type": "event",
                    "data": {
                        "log": log_entry,
                        "event_type": event_type,
                        "file": file_path,
                        "user": user,
                        "is_anomaly": is_anomaly,
                        "is_canary": is_canary,
                        "risk": risk_result,
                        "chains": chains,
                        "ts": time.time(),
                    }
                })

                # Broadcast updated risk scores
                await _broadcast({"type": "risk_update", "data": risk_engine.get_all_risks()})

                # Broadcast chains
                if chains:
                    await _broadcast({"type": "chains", "data": chains})

                # Broadcast new alerts
                alerts = [a for a in risk_engine.get_alerts(5) if time.time() - a.get("ts", 0) < 3]
                if alerts:
                    await _broadcast({"type": "new_alerts", "data": alerts})
            else:
                # Just broadcast the heartbeat log
                await _broadcast({"type": "log", "data": log_entry})

            if "CREATED" in log_entry or "DELETED" in log_entry:
                await asyncio.sleep(0.5)
                await _broadcast({"type": "tree", "data": get_file_tree()})

        await asyncio.sleep(0.1)


async def broadcast_stats():
    """Periodically push CPU/RAM and aggregate stats."""
    while True:
        if active_connections:
            await _broadcast({
                "type": "stats",
                "data": {
                    "cpu": psutil.cpu_percent(interval=None),
                    "ram": psutil.virtual_memory().percent,
                }
            })
        await asyncio.sleep(1)


async def cluster_refresh():
    """Periodically retrain role clusters and push to clients."""
    while True:
        await asyncio.sleep(30)
        vectors = behavioral_engine.get_feature_vectors()
        if len(vectors) >= role_clusterer.K:
            role_clusterer.fit(vectors)
            assignments = role_clusterer.get_all_assignments(vectors)
            await _broadcast({"type": "clusters", "data": assignments})


def start_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    loop.create_task(broadcast_logs())
    loop.create_task(broadcast_stats())
    loop.create_task(cluster_refresh())
    loop.run_until_complete(server.serve())
