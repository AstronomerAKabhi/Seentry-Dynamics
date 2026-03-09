<div align="center">

# 🛡️ Sentry Dynamics
### Behavioral File Integrity Monitor

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=flat-square&logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

> Real-time file integrity monitoring with active honeypot defense, process attribution, and a live WebSocket dashboard.

</div>

---

## 📌 Overview

**Sentry Dynamics** is a Behavioral File Integrity Monitor (FIM) that detects unauthorized file activity in real time. Unlike passive logging tools, it combines:

- 🔍 **Continuous polling** — detects file CREATE, MODIFY, and DELETE events within 250ms
- 🪤 **Active honeypot defense** — deploys hidden canary files that trigger critical alerts the moment an intruder touches them
- 🧠 **Process attribution** — identifies the responsible process using `psutil`
- 📊 **Live dashboard** — real-time WebSocket-powered UI with topology graph, system logs, and CPU/RAM metrics

---

## 🏗️ Architecture

```
start_fim.bat
└── main.py
    ├── Thread 1 → monitor.py          # Polls filesystem every 250ms
    │   ├── canary.py                  # Deploys & tracks honeypot files
    │   ├── analyzer.py                # Attributes events to processes
    │   └── fim_logger.py              # Logs to file + console + WS queue
    │
    └── Thread 2 → server.py           # FastAPI + WebSocket server
        └── templates/dashboard.html   # Real-time browser dashboard
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚨 **Canary Trap** | 11 hidden honeypot files deployed at startup; any access triggers a CRITICAL alert with alarm sound |
| ⚡ **Fast Detection** | 250ms polling interval for near-instant event capture |
| 🌐 **Live Dashboard** | WebSocket-driven UI — no refresh needed |
| 🗺️ **Directory Topology** | D3.js force graph visualizing the monitored file tree in real time |
| 📈 **Performance Metrics** | Live CPU and RAM usage graph |
| 🔊 **Alert Sound** | Audio alarm fires instantly on canary trigger |
| 🧹 **Auto Cleanup** | All canary files are removed cleanly on shutdown |

---

## 🚀 Quick Start

### Prerequisites

```bash
pip install -r requirements.txt
```

### Run

**Windows** — just double-click:
```
start_fim.bat
```

Or run manually:
```bash
python main.py
```

The dashboard opens automatically at **http://localhost:8000**

---

## 🧪 Testing

With the FIM running, open the `test_monitored\` folder and:

| Action | Expected Result |
|--------|----------------|
| Create a new `.txt` file | `CREATED` event appears in System Logs |
| Write to / save the file | `MODIFIED` event appears in System Logs |
| Delete the file | `DELETED` event appears in System Logs |
| Open `passwords.txt` (canary) | 🚨 Red CRITICAL alert + alarm sound fires |

> **Tip:** Canary files are hidden on Windows. Use *Show hidden items* in Explorer or `Get-ChildItem -Force` in PowerShell to see them.

---

## 📁 Project Structure

```
Seentry-Dynamics/
├── main.py               # Entry point — starts monitor + server threads
├── monitor.py            # Core FIM polling engine (250ms interval)
├── analyzer.py           # Process attribution via psutil
├── canary.py             # Honeypot file manager
├── config.py             # Directory watch list & log path config
├── fim_logger.py         # Multi-output logger (file, console, WebSocket)
├── server.py             # FastAPI server + WebSocket broadcast
│
├── templates/
│   └── dashboard.html    # Real-time monitoring dashboard
│
├── test_monitored/       # Watched directory (canaries deployed here at runtime)
│
├── verify_fim.py         # Integration test: file event detection
├── verify_canary.py      # Integration test: canary trap mechanism
├── verify_ui.py          # Integration test: dashboard accessibility
│
├── debug_monitor.py      # Development utility: manual polling loop
├── create_ppt.py         # Generates project presentation (.pptx)
├── create_report.py      # Generates project report (.docx)
│
├── requirements.txt
├── start_fim.bat         # One-click Windows launcher
└── README.md
```

---

## 🛠️ How It Works

### 1. File Monitoring
`monitor.py` uses `os.walk()` to scan the watched directory every **250ms**, comparing file modification times (`mtime`) against a known-state dictionary. Changes are classified as `CREATED`, `MODIFIED`, or `DELETED`.

### 2. Canary / Honeypot Defense
On startup, `canary.py` writes **11 hidden decoy files** (`passwords.txt`, `admin_creds.xml`, `private_keys.pem`, etc.) into the watched directory. File attributes are reset before each write to ensure clean re-deployment even after unclean shutdowns. Any event on a canary path fires a `CRITICAL` log entry immediately.

### 3. Dashboard
`server.py` exposes a **FastAPI** app on port `8000`. A background asyncio loop drains the log queue and broadcasts JSON messages over WebSocket to all connected browsers. The frontend renders:
- **System Logs** — scrollable timestamped event feed
- **Directory Topology** — live D3.js force graph of the file tree
- **Performance Metrics** — rolling CPU/RAM chart (Canvas API)
- **Activity Feed** — recent file events panel

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework & WebSocket server |
| `uvicorn[standard]` | ASGI server |
| `psutil` | Process attribution & system metrics |
| `websockets` | WebSocket support |
| `jinja2` | HTML template rendering |
| `requests` | HTTP client (used in verification tests) |
| `python-pptx` | Presentation generation |
| `python-docx` | Report generation |

---

## 🔒 Security Notes

- Canary files are **hidden** on Windows (`SetFileAttributesW`) so they blend into the environment
- The `test_monitored/` directory is excluded from version control — canary files are always freshly generated at runtime
- `.env` files are git-ignored; never commit secrets

---

## 👤 Author

**Abhishek P** — Department of Computer Science  
Project: *Behavioral File Integrity Monitoring with Active Defense*

---

<div align="center">
  <sub>Built with ❤️ — Sentry Dynamics | Behavioral FIM</sub>
</div>
