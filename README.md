<div align="center">

# 🛡️ Seentry-Dynamics
### Advanced AI-Powered Behavioral File Integrity Monitoring (FIM)

[![Python Support](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

<br/>

Traditional File Integrity Monitoring (FIM) systems generate overwhelming operational noise due to hardcoded, static rules. **Seentry-Dynamics** reinvents FIM by applying Artificial Intelligence and Machine Learning to understand the *context* surrounding file modifications. By learning the normal behavioral baseline of users and roles, Seentry-Dynamics significantly reduces false positives and highlights genuine, complex anomalous threats. 

---

## ✨ Key Features

- **Context-Aware ML Anomaly Detection**: Uses Isolation Forest to weed out benign administrative tasks from actual malicious activity.
- **Dynamic Risk Scoring**: Evaluates the real-time risk of individual users based on their deviation from established baselines.
- **Role-Based Clustering**: Employs K-Means algorithms to dynamically group users and identify outliers within specific peer groups.
- **Advanced Correlation Engine**: Detects distributed, low-and-slow attack patterns over time.
- **Interactive Forensic Dashboard**: A visually striking, real-time web interface for rapid incident response and threat hunting.
- **Active Canary Traps**: Immediate, high-priority alerting upon access to synthetic "honey-files" mimicking sensitive assets.

---

## 🚀 Quick Start Guide

### How to Run

1. **Start the System**:
   Double-click the `start_fim.bat` file in the root directory.
   - It will open a black terminal window representing the **FIM Core Engine**.
   - It will automatically launch your default web browser and navigate directly to the **Threat Dashboard**.

### Testing the Defenses

The system automatically creates a `test_monitored` folder upon initialization. You can use it to test the capabilities of Seentry-Dynamics:

- **Create a File**: Add a new file in the directory and watch the Dashboard log capture the event in real-time.
- **Modify a File**: Alter the contents of an existing file (e.g., `test_file.txt`) and observe the AI analyze the change.
- **Trigger the Canary**: Open or modify the `passwords.txt` file. You will immediately hear an audible alarm and see a critical Red Alert triggered on the Dashboard.

### Stopping the Agent

- To gracefully shut down the monitoring agent, simply close the **FIM Core** terminal window.

---

## 📊 Presentation & Reporting

Generate comprehensive documentation automatically:
- Run `python create_ppt.py` to generate the project presentation slides.
- Run `python create_report.py` to generate the detailed project technical report.

*(Additionally, `create_hackathon_ppt.py` provides a pitch-deck styled presentation template).*

---
<div align="center">
<i>Protect your critical infrastructure with intelligence, not just rules.</i>
</div>
