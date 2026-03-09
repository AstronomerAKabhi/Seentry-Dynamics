import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import json
import psutil
from fim_logger import log_queue
from config import DIRECTORIES_TO_WATCH

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

templates = Jinja2Templates(directory=TEMPLATES_DIR)

active_connections: set[WebSocket] = set()
log_history: list[str] = []


def build_node(path: str) -> dict:
    """Recursively builds a JSON tree node for the given directory path."""
    node = {"name": os.path.basename(path), "path": path, "type": "folder", "children": []}
    try:
        for entry in os.scandir(path):
            if entry.is_dir():
                node["children"].append(build_node(entry.path))
            else:
                node["children"].append({"name": entry.name, "path": entry.path, "type": "file"})
    except PermissionError:
        pass
    return node


def get_file_tree() -> dict:
    """Generates a JSON tree of the monitored directories."""
    tree = {"name": "Root", "children": []}
    for directory in DIRECTORIES_TO_WATCH:
        if os.path.exists(directory):
            tree["children"].append(build_node(directory))
    return tree


async def broadcast_to_all(message: str):
    """Sends a message to all active WebSocket connections, pruning dead ones."""
    dead = set()
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception:
            dead.add(connection)
    active_connections.difference_update(dead)


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)

    try:
        tree = get_file_tree()
        await websocket.send_text(json.dumps({"type": "tree", "data": tree}))
    except Exception:
        pass

    for msg in log_history:
        try:
            await websocket.send_text(msg)
        except Exception:
            pass

    try:
        while True:
            await websocket.receive_text()
    except Exception:
        active_connections.discard(websocket)


async def broadcast_logs():
    """Reads from the log queue and broadcasts to all connected clients."""
    tree_update_needed = False
    while True:
        while not log_queue.empty():
            log_entry = log_queue.get()
            message = json.dumps({"type": "log", "data": log_entry})

            log_history.append(message)
            if len(log_history) > 50:
                log_history.pop(0)

            await broadcast_to_all(message)

            if "CREATED" in log_entry or "DELETED" in log_entry:
                tree_update_needed = True

        if tree_update_needed and active_connections:
            await asyncio.sleep(0.5)
            try:
                tree = get_file_tree()
                await broadcast_to_all(json.dumps({"type": "tree", "data": tree}))
            except Exception as e:
                pass
            tree_update_needed = False

        await asyncio.sleep(0.1)


async def broadcast_stats():
    """Broadcasts system statistics to all connected clients."""
    while True:
        if active_connections:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            message = json.dumps({"type": "stats", "data": {"cpu": cpu, "ram": ram}})
            await broadcast_to_all(message)
        await asyncio.sleep(1)


def start_server():
    """Starts the FastAPI server with background broadcast tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)

    loop.create_task(broadcast_logs())
    loop.create_task(broadcast_stats())
    loop.run_until_complete(server.serve())
