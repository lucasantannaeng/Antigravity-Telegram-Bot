# 🌌 Antigravity Telegram Bot v6.1 (Ultimate Edition)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-2CA5E0?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![Google Antigravity](https://img.shields.io/badge/Antigravity-CLI%20v1.1-purple.svg)]()
[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent%20Integrated-emerald.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **High-resilience 24/7 Always-On daemon integrating the Google Antigravity CLI (`agy`) with bidirectional multi-agent communication to the Hermes Agent, neural voice synthesis, memory sentinel watchdog, and interactive terminal DevOps.**

---

## 🚀 Key Architectural Highlights

* 📂 **Interactive File Explorer (`/browse`)**: Visual directory navigation and syntax-highlighted code inspection directly through inline buttons in Telegram.
* ⚙️ **Multi-Agent Modes (`/mode`)**: Instant toggle between `Build` (full autonomous execution), `Plan` (read-only architecture & planning), and `Audit` (security & code review).
* 🛡️ **Guardian AI**: Predictive interception and double-confirmation protection against destructive terminal commands (`rmdir /s`, `del /s /q`, `Format-Volume`).
* 🩺 **Subsystem Doctor (`/doctor`)**: Real-time diagnostic health audit of Telegram API latency, Groq/Gemini endpoints, SQLite integrity, and hardware metrics.
* 🛡️ **24/7 Sentinel Watchdog**: Proactive memory management (`gc.collect()` + SQLite `PRAGMA shrink_memory`) maintaining process RAM strictly **< 70MB**.
* ⚡ **Local Metrics Micro-Server**: High-performance multithreaded HTTP JSON endpoint on `http://127.0.0.1:8765/metrics`.
* 🧠 **Dynamic Complexity Query Router**: Routes fast requests to `Gemini 3.7 Flash` and complex refactoring to `Gemini 3.1 Pro (High)`.
* 💻 **Integrated DevOps Suite**: `/run`, `/git`, `/diff`, `/commit`, `/cd`, `/ls`, `/cat` directly from your Telegram chat.
* 🎙️ **Neural Voice Pipeline**: Sub-300ms Speech-to-Text via **Groq Whisper Turbo** + natural neural Text-to-Speech via **EdgeTTS** (`pt-BR-AntonioNeural` / `pt-BR-FranciscaNeural`).
* 📋 **Multi-Agent Blackboard**: Persistent SQLite-backed task sharing and synchronization between Google Antigravity and Hermes Agent.
* 🔄 **24/7 Windows Boot Persistence**: Headless background initialization on system startup via VBS and Windows Task Scheduler.

---

## 📋 Command Reference

| Command | Description |
| :--- | :--- |
| `/start` | Open main interactive menu with quick action buttons |
| `/browse` | Visual file and folder explorer with inline buttons |
| `/mode` | Toggle agent execution mode (`Build`, `Plan`, `Audit`) |
| `/doctor` | End-to-end subsystem health audit and latency benchmark |
| `/status` / `/sys` | Hardware diagnostics: CPU, RAM, disk, and database integrity |
| `/history` | Execution history, latency logs, and recent agent tasks |
| `/model` | Interactive LLM model selector |
| `/voice` | Toggle automatic natural voice responses (EdgeTTS) |
| `/run <cmd>` | Execute PowerShell commands in workspace with Guardian AI safety |
| `/cd <dir>` | Change active workspace directory |
| `/ls [dir]` | List directory contents |
| `/cat <file>` | Display file contents with syntax formatting |
| `/git [cmd]` | Execute Git commands (`status`, `log`, `diff`) |
| `/diff [file]` | View pending Git diff changes |
| `/commit <msg>`| Stage all changes (`git add -A`) and create commit |
| `/tasks` | View multi-agent shared blackboard tasks |
| `/hermes <msg>`| Delegate task directly to Hermes Agent |
| `/shutdown` | Gracefully terminate daemon (requires Guardian confirmation) |
| `/reset` | Clear session conversation context |

---

## ⚙️ 24/7 Windows Boot Persistence

The daemon starts automatically in headless background mode upon system startup through:
- `C:\Users\Luca Rodrigues\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Antigravity_Telegram_Bot.vbs`
- Windows Task Scheduler: `Antigravity_Telegram_Bot_Logon`

### Manual Execution

```powershell
# Start daemon in terminal
python bot.py

# Run comprehensive endurance & stress suite
python stress_test.py

# Run subsystem health diagnostic
python doctor.py
```

---

## 📄 License

MIT License — Copyright (c) 2026 Luca Rodrigues Gomes de Sant'Anna. See [LICENSE](LICENSE) for details.
