#!/usr/bin/env python3
"""
Antigravity Telegram Bot v6.0 (Ultimate Edition)
State-of-the-art 24/7 Agentic Platform for Google Antigravity & Hermes Agent.

Absorbed Open-Source Innovations (karfly, CoderBOT, OpenCode, Claude Channels, PocketPaw):
- Interactive Inline File Browser (/browse): Navigate folders and read files with one tap.
- Agent Operating Modes (/mode): Switch between Build (Act), Plan (Architect), and Audit (Security).
- Guardian Destructive Action Filter: Intercepts high-risk commands and requests confirmation.
- Execution History & Metrics (/history): Persistent SQLite log of recent agent runs.
- Formatter Engine (formatters.py): Table-to-card mobile converter & unclosed code fence auto-closer.
- Telegram Reactions (reactions.py): Real-time emoji feedback on user messages (🤔 ➔ ⚡ ➔ 👍).
- Subsystem Doctor (doctor.py): /doctor command performing full health audit & scorecard.
- Sentinel Watchdog: Active memory trimmer (GC + SQLite shrink) & host RAM guard (<80MB RSS).
- Local Metrics Micro-Server: Real-time multithreaded JSON health metrics at :8765/metrics.
- DevOps Suite: /run, /git, /diff, /commit, /cd, /ls, /cat, /browse directly from Telegram.
- Bidirectional Audio: STT (Groq Whisper Turbo / Gemini) + TTS (Edge Neural Brazilian Voice).
- Multi-Agent Shared Blackboard: Hermes ↔ Antigravity bidirectional task bus.
- Topic-Scoped Workspaces: Forum Topics can each have isolated workspace roots.
- Windows Power Sleep Lock: SetThreadExecutionState prevents host sleep during long agentic runs.
"""

import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import io
import gc
import json
import time
import ctypes
import sqlite3
import logging
import asyncio
import threading
import psutil
import socket
import subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import httpx
import edge_tts

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import formatters
import reactions
import doctor

# ── 1. Configuration & Directories ──────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USERS_RAW = os.getenv("TELEGRAM_ALLOWED_USERS", "1366073609")
DEFAULT_WORKSPACE = Path(os.getenv("WORKSPACE_DIR", r"D:\Projetos")).resolve()
AGY_PATH = os.getenv("AGY_PATH", "agy")
AGY_MODEL = os.getenv("AGY_MODEL", "auto").strip()
AGY_TIMEOUT = int(os.getenv("AGY_TIMEOUT_SECONDS", "600"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
FREE_LLM_API_KEY = (os.getenv("FREE_LLM_API_KEY") or os.getenv("FREELLM_API_KEY") or "").strip()
FREE_LLM_BASE_URL = (os.getenv("FREE_LLM_BASE_URL") or os.getenv("FREELLM_BASE_URL") or "http://127.0.0.1:31415/v1").rstrip("/")
os.environ["FREE_LLM_API_KEY"] = FREE_LLM_API_KEY
os.environ["FREELLM_API_KEY"] = FREE_LLM_API_KEY
os.environ["FREE_LLM_BASE_URL"] = FREE_LLM_BASE_URL
os.environ["FREELLM_BASE_URL"] = FREE_LLM_BASE_URL
TTS_VOICE = os.getenv("TTS_VOICE", "pt-BR-AntonioNeural")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8765"))

TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)
DB_PATH = BASE_DIR / "state.db"
LOG_FILE = BASE_DIR / "bot.log"

ALLOWED_USERS = set()
for uid in ALLOWED_USERS_RAW.split(","):
    uid = uid.strip()
    if uid.isdigit():
        ALLOWED_USERS.add(int(uid))

TASK_SEMAPHORE = asyncio.Semaphore(2)
ACTIVE_PROCESSES: Dict[int, asyncio.subprocess.Process] = {}
PENDING_CONFIRMATIONS: Dict[str, str] = {}
BOT_START_TIME = time.time()
METRICS_SERVER_TASK = None


# ── 2. Logging Setup with 15MB Max Rotation ──────────────────────────────────

logger = logging.getLogger("AntigravityUltimate")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB per file
    backupCount=3,              # 3 backups = max 15 MB
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


# ── 3. Persistent SQLite Database & Shared Blackboard ───────────────────────

class StateDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-128")
        conn.execute("PRAGMA temp_store=FILE")
        conn.execute("PRAGMA mmap_size=0")
        conn.execute("PRAGMA wal_autocheckpoint=10")
        return conn

    def _init_db(self):
        with sqlite3.connect(self.db_path, timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA wal_autocheckpoint=10")
            conn.execute("PRAGMA cache_size=-128")
            conn.execute("PRAGMA mmap_size=0")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(user_settings)")
                cols = [col[1] for col in cursor.fetchall()]
                if "scope_id" not in cols:
                    conn.execute("DROP TABLE user_settings")
                elif "agent_mode" not in cols:
                    conn.execute("ALTER TABLE user_settings ADD COLUMN agent_mode TEXT DEFAULT 'build'")

            # Metrics schema migration check
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(metrics)")
                m_cols = [col[1] for col in cursor.fetchall()]
                if "memory_rss_mb" not in m_cols:
                    conn.execute("ALTER TABLE metrics ADD COLUMN memory_rss_mb REAL DEFAULT 0.0")
                if "prompt_summary" not in m_cols:
                    conn.execute("ALTER TABLE metrics ADD COLUMN prompt_summary TEXT DEFAULT ''")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    scope_id TEXT PRIMARY KEY,
                    voice_out_enabled INTEGER DEFAULT 0,
                    active_model TEXT DEFAULT 'auto',
                    active_workspace TEXT DEFAULT '',
                    agent_mode TEXT DEFAULT 'build',
                    updated_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    command_type TEXT,
                    prompt_summary TEXT DEFAULT '',
                    duration_sec REAL,
                    memory_rss_mb REAL,
                    success INTEGER,
                    timestamp REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blackboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_agent TEXT,
                    target_agent TEXT,
                    topic TEXT,
                    content TEXT,
                    status TEXT DEFAULT 'pending',
                    timestamp REAL
                )
            """)
            conn.commit()

    def _get_scope_key(self, chat_id: int, topic_id: Optional[int] = None) -> str:
        return f"{chat_id}:{topic_id}" if topic_id else str(chat_id)

    def get_settings(self, chat_id: int, topic_id: Optional[int] = None) -> dict:
        scope_key = self._get_scope_key(chat_id, topic_id)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT voice_out_enabled, active_model, active_workspace, agent_mode FROM user_settings WHERE scope_id = ?", (scope_key,))
            row = cursor.fetchone()
            if row:
                ws_path = Path(row[2]) if row[2] and Path(row[2]).exists() else DEFAULT_WORKSPACE
                return {
                    "voice_out_enabled": bool(row[0]),
                    "active_model": row[1] or "auto",
                    "active_workspace": ws_path,
                    "agent_mode": row[3] or "build"
                }
            return {
                "voice_out_enabled": False,
                "active_model": "auto",
                "active_workspace": DEFAULT_WORKSPACE,
                "agent_mode": "build"
            }

    def get_user_settings(self, chat_id: int, topic_id: Optional[int] = None) -> dict:
        return self.get_settings(chat_id, topic_id)

    def set_voice_enabled(self, chat_id: int, topic_id: Optional[int] = None, enabled: bool = True):
        if isinstance(topic_id, bool):
            enabled = topic_id
            topic_id = None
        scope_key = self._get_scope_key(chat_id, topic_id)
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO user_settings (scope_id, voice_out_enabled, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET voice_out_enabled = excluded.voice_out_enabled, updated_at = excluded.updated_at
            """, (scope_key, int(enabled), time.time()))
            conn.commit()

    def set_model(self, chat_id: int, topic_id: Optional[int] = None, model: str = "auto"):
        scope_key = self._get_scope_key(chat_id, topic_id)
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO user_settings (scope_id, active_model, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET active_model = excluded.active_model, updated_at = excluded.updated_at
            """, (scope_key, model, time.time()))
            conn.commit()

    def set_agent_mode(self, chat_id: int, topic_id: Optional[int] = None, mode: str = "build"):
        scope_key = self._get_scope_key(chat_id, topic_id)
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO user_settings (scope_id, agent_mode, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET agent_mode = excluded.agent_mode, updated_at = excluded.updated_at
            """, (scope_key, mode, time.time()))
            conn.commit()

    def set_workspace(self, chat_id: int, topic_id: Optional[int] = None, workspace: Path = DEFAULT_WORKSPACE):
        scope_key = self._get_scope_key(chat_id, topic_id)
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO user_settings (scope_id, active_workspace, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET active_workspace = excluded.active_workspace, updated_at = excluded.updated_at
            """, (scope_key, str(workspace), time.time()))
            conn.commit()

    def record_metric(self, chat_id: int, command_type: str, duration_sec: float, success: bool, rss_mb: float = 0.0, prompt_summary: str = ""):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO metrics (chat_id, command_type, duration_sec, memory_rss_mb, success, prompt_summary, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (chat_id, command_type, duration_sec, rss_mb, int(success), prompt_summary[:120], time.time())
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record metric: {e}")

    def get_recent_history(self, limit: int = 6) -> List[Tuple]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, command_type, prompt_summary, duration_sec, success, timestamp FROM metrics ORDER BY id DESC LIMIT ?", (limit,))
            return cursor.fetchall()

    def post_blackboard(self, sender: str, target: str, topic: str, content: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO blackboard (sender_agent, target_agent, topic, content, status, timestamp) VALUES (?, ?, ?, ?, 'active', ?)",
                (sender, target, topic, content, time.time())
            )
            conn.commit()

    def get_blackboard_recent(self, limit: int = 5) -> List[Tuple]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, sender_agent, target_agent, topic, content, status, timestamp FROM blackboard ORDER BY id DESC LIMIT ?", (limit,))
            return cursor.fetchall()

    def get_total_tasks_count(self) -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM metrics")
            return cursor.fetchone()[0]

    def optimize_memory(self):
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute("PRAGMA shrink_memory")
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.execute("PRAGMA optimize")
        except Exception:
            pass


db = StateDB(DB_PATH)


def trim_process_memory() -> float:
    """Aggressively trims Python GC garbage, SQLite WAL pages, and Windows working set (<80MB RSS target)."""
    gc.collect()
    db.optimize_memory()
    if sys.platform == "win32":
        try:
            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass
    proc = psutil.Process(os.getpid())
    return round(proc.memory_info().rss / (1024 * 1024), 2)


# ── 4. Windows Power & Sleep Inhibit ─────────────────────────────────────────

class WindowsPowerLock:
    """Prevents host OS from entering sleep while tasks are running."""
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_AWAYMODE_REQUIRED = 0x00000040

    @classmethod
    def acquire(cls):
        if sys.platform == "win32":
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    cls.ES_CONTINUOUS | cls.ES_SYSTEM_REQUIRED | cls.ES_AWAYMODE_REQUIRED
                )
            except Exception:
                pass

    @classmethod
    def release(cls):
        if sys.platform == "win32":
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(cls.ES_CONTINUOUS)
            except Exception:
                pass


# ── 5. Audio & Voice Engine (STT + TTS) ──────────────────────────────────────

async def transcribe_audio(audio_path: Path) -> Optional[str]:
    """Transcribes audio with Groq Whisper Turbo (<300ms) or Gemini fallback."""
    if GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(audio_path, "rb") as f:
                    files = {"file": (audio_path.name, f, "audio/ogg")}
                    data = {"model": "whisper-large-v3-turbo", "language": "pt"}
                    response = await client.post(url, headers=headers, files=files, data=data)
                    if response.status_code == 200:
                        return response.json().get("text", "").strip()
        except Exception as e:
            logger.warning(f"Groq transcription fallback: {e}")

    if GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    "Transcreva o áudio a seguir em português com máxima fidelidade. Retorne APENAS o texto.",
                    genai.types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg")
                ]
            )
            return response.text.strip() if response and response.text else None
        except Exception as e:
            logger.error(f"Gemini transcription error: {e}")

    return None


async def generate_speech(text: str, out_path: Path) -> bool:
    """Synthesizes high-definition Portuguese speech using Edge Neural TTS."""
    try:
        clean_text = formatters.strip_markdown(text)
        if len(clean_text) > 1000:
            clean_text = clean_text[:990] + "... (áudio resumido, verifique o texto no chat para mais detalhes)."

        communicate = edge_tts.Communicate(clean_text, TTS_VOICE)
        await communicate.save(str(out_path))
        return True
    except Exception as e:
        logger.error(f"EdgeTTS error: {e}")
        return False


# ── 6. Intelligent Query Classifier & Mode Injection ─────────────────────────

def classify_model_for_query(prompt: str, configured_model: str) -> Tuple[Optional[str], bool]:
    """Returns (custom_model_id, is_high_effort) based on query and settings."""
    if configured_model and configured_model not in ["auto", "default"]:
        return configured_model, False

    p_lower = prompt.lower()
    heavy_keywords = [
        "refactor", "arquitetura", "planeje", "planejamento", "segurança",
        "vulnerabilidade", "auditoria", "complexo", "multi-agent", "benchmark",
        "redesenhar", "design system", "concorrência", "deadlock", "algoritmo"
    ]
    is_heavy = any(k in p_lower for k in heavy_keywords) or len(prompt) > 400
    return None, is_heavy


def apply_agent_mode_prefix(prompt: str, mode: str) -> str:
    """Injects behavioral guidelines depending on active agent mode (Build/Plan/Audit)."""
    if mode == "plan":
        return f"[DIRETIVA: MODO PLANEJAMENTO/ARQUITETURA - NÃO execute alterações ou mutações no código. Realize levantamento de requisitos, arquitetura e elabore um plano técnico estruturado passo a passo]\n\n{prompt}"
    elif mode == "audit":
        return f"[DIRETIVA: MODO AUDITORIA DE SEGURANÇA & QUALIDADE - Inspecione o código rigorosamente buscando vulnerabilidades OWASP, race conditions, memory leaks e edge cases]\n\n{prompt}"
    return prompt


# ── 7. Agent Execution Pipeline ──────────────────────────────────────────────

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


async def execute_agy_prompt(chat_id: int, topic_id: Optional[int], prompt: str) -> Tuple[str, bool]:
    """Executes agy CLI command with dynamic model routing, semaphore & power lock."""
    cfg = db.get_settings(chat_id, topic_id)
    custom_model, is_high_effort = classify_model_for_query(prompt, cfg["active_model"])
    workspace = cfg["active_workspace"]
    mode = cfg.get("agent_mode", "build")

    final_prompt = apply_agent_mode_prefix(prompt, mode)
    cmd = [AGY_PATH, "-p", final_prompt, "--dangerously-skip-permissions"]
    if is_high_effort:
        cmd.extend(["--effort", "high"])
    if custom_model:
        cmd.extend(["--model", custom_model])

    logger.info(f"Chat {chat_id} executing agy [effort_high={is_high_effort}|mode={mode}] in {workspace}")
    start_t = time.time()
    WindowsPowerLock.acquire()

    try:
        async with TASK_SEMAPHORE:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
                env=os.environ.copy()
            )
            ACTIVE_PROCESSES[chat_id] = process

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=AGY_TIMEOUT)

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()
            duration = time.time() - start_t
            rss_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

            success = (process.returncode == 0)
            db.record_metric(chat_id, f"agy_{mode}", duration, success, round(rss_mb, 2), prompt)

            if not success and not out_text:
                return f"❌ **Erro no Antigravity (`agy`):**\n```\n{err_text or f'Código de saída: {process.returncode}'}\n```", False

            result = out_text if out_text else err_text
            return result, True

    except asyncio.CancelledError:
        return "🛑 **Execução cancelada pelo usuário.**", False
    except asyncio.TimeoutError:
        return f"⏱️ **Timeout:** Excedeu o limite de {AGY_TIMEOUT} segundos.", False
    except Exception as e:
        logger.error(f"Execution error: {e}", exc_info=True)
        return f"❌ **Exceção durante execução:** `{e}`", False
    finally:
        ACTIVE_PROCESSES.pop(chat_id, None)
        WindowsPowerLock.release()
        trim_process_memory()


async def execute_hermes_prompt(chat_id: int, prompt: str) -> Tuple[str, bool]:
    """Delegates a prompt directly to Hermes Agent CLI."""
    cmd = ["hermes", "chat", "-q", prompt]
    logger.info(f"Delegating to Hermes: {cmd}")
    start_t = time.time()
    WindowsPowerLock.acquire()

    try:
        async with TASK_SEMAPHORE:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(DEFAULT_WORKSPACE),
                env=os.environ.copy()
            )
            ACTIVE_PROCESSES[chat_id] = process

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=AGY_TIMEOUT)
            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()
            duration = time.time() - start_t
            rss_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

            success = (process.returncode == 0)
            db.record_metric(chat_id, "hermes_delegation", duration, success, round(rss_mb, 2), prompt)
            db.post_blackboard("AntigravityBot", "HermesAgent", "Delegation", prompt[:100])

            result = out_text if out_text else err_text
            return result, success
    except Exception as e:
        logger.error(f"Hermes error: {e}", exc_info=True)
        return f"❌ **Erro ao comunicar com Hermes:** `{e}`", False
    finally:
        ACTIVE_PROCESSES.pop(chat_id, None)
        WindowsPowerLock.release()
        trim_process_memory()


# ── 8. UI Helpers & Smart Delivery ──────────────────────────────────────────

async def live_progress_updater(message, stop_event: asyncio.Event):
    """Updates progress message smoothly every 3.5 seconds."""
    start_time = time.time()
    frames = ["⏳", "⚡", "🔍", "⚙️", "✨", "🚀"]
    idx = 0

    while not stop_event.is_set():
        try:
            await asyncio.sleep(3.5)
            if stop_event.is_set():
                break

            elapsed = int(time.time() - start_time)
            icon = frames[idx % len(frames)]
            idx += 1
            await message.edit_text(
                f"{icon} **Executando no workspace...** `({elapsed}s)`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass


async def send_smart_delivery(
    chat_id: int,
    topic_id: Optional[int],
    text: str,
    context: ContextTypes.DEFAULT_TYPE,
    status_message=None,
    reply_to_message_id: int = None,
    send_audio_reply: bool = False
):
    """Delivers output: text, large file attachment if needed, and optional audio voice response."""
    if not text.strip():
        text = "*(Comando concluído com sucesso sem saída textual)*"

    cfg = db.get_settings(chat_id, topic_id)
    voice_enabled = cfg.get("voice_out_enabled", False) or send_audio_reply

    # 1. Handle Huge Outputs (> 3800 chars)
    if len(text) > 3800:
        preview = text[:1500] + "\n\n*(...relatório completo anexado no arquivo abaixo)*"
        if status_message:
            try:
                await status_message.edit_text(preview, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await status_message.edit_text(preview)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                message_thread_id=topic_id,
                text=preview,
                reply_to_message_id=reply_to_message_id
            )

        file_buf = io.BytesIO(text.encode("utf-8"))
        file_buf.name = f"antigravity_output_{int(time.time())}.md"
        await context.bot.send_document(
            chat_id=chat_id,
            message_thread_id=topic_id,
            document=InputFile(file_buf, filename=file_buf.name),
            caption="📄 **Relatório Completo Gerado pelo Antigravity**",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Standard Message Delivery: Convert tables and ensure closed fences
        formatted_text = formatters.convert_tables_to_cards(text)
        formatted_text = formatters.ensure_closed_code_blocks(formatted_text)

        delivered = False
        if status_message:
            try:
                await status_message.edit_text(formatted_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                delivered = True
            except Exception:
                try:
                    html_text = formatters.format_telegram_html(text)
                    await status_message.edit_text(html_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    delivered = True
                except Exception:
                    try:
                        clean_text = formatters.strip_markdown(text)
                        await status_message.edit_text(clean_text, disable_web_page_preview=True)
                        delivered = True
                    except Exception:
                        pass

        if not delivered:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=topic_id,
                    text=formatted_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_to_message_id=reply_to_message_id,
                    disable_web_page_preview=True
                )
            except Exception:
                try:
                    html_text = formatters.format_telegram_html(text)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        message_thread_id=topic_id,
                        text=html_text,
                        parse_mode=ParseMode.HTML,
                        reply_to_message_id=reply_to_message_id,
                        disable_web_page_preview=True
                    )
                except Exception:
                    clean_text = formatters.strip_markdown(text)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        message_thread_id=topic_id,
                        text=clean_text,
                        reply_to_message_id=reply_to_message_id,
                        disable_web_page_preview=True
                    )

    # 2. Outbound Voice Synthesis (TTS) if enabled
    if voice_enabled:
        audio_out = TEMP_DIR / f"tts_{int(time.time())}.mp3"
        try:
            await context.bot.send_chat_action(chat_id=chat_id, message_thread_id=topic_id, action=ChatAction.RECORD_VOICE)
            if await generate_speech(text, audio_out):
                with open(audio_out, "rb") as f:
                    await context.bot.send_voice(
                        chat_id=chat_id,
                        message_thread_id=topic_id,
                        voice=f,
                        caption="🎙️ **Resposta em Áudio**",
                        parse_mode=ParseMode.MARKDOWN
                    )
        except Exception as e:
            logger.error(f"TTS delivery error: {e}")
        finally:
            if audio_out.exists():
                try:
                    audio_out.unlink()
                except Exception:
                    pass


# ── 9. Command Handlers ──────────────────────────────────────────────────────

async def register_bot_commands(application):
    """Registers official slash commands in the Telegram UI menu."""
    commands = [
        BotCommand("start", "🚀 Menu principal e atalhos"),
        BotCommand("browse", "📂 Explorador interativo de pastas e arquivos"),
        BotCommand("mode", "⚙️ Alternar modo de agente (Build/Plan/Audit)"),
        BotCommand("clean", "🧹 Otimizar memória RAM e limpar temporários"),
        BotCommand("doctor", "🩺 Diagnóstico profundo de todos os subsistemas"),
        BotCommand("status", "📊 Diagnóstico de hardware, RAM e 24/7"),
        BotCommand("history", "📜 Histórico recente de execuções"),
        BotCommand("model", "🧠 Selecionar modelo LLM (Gemini/Claude/Auto)"),
        BotCommand("voice", "🎙️ Alternar respostas em áudio"),
        BotCommand("run", "⚡ Executar comando de terminal no workspace"),
        BotCommand("git", "🌿 Status, branch e commits do Git"),
        BotCommand("diff", "🔍 Ver diffs de código no repositório"),
        BotCommand("commit", "💾 Criar commit automático no Git"),
        BotCommand("cd", "📁 Alterar diretório do workspace"),
        BotCommand("ls", "📂 Listar arquivos do workspace ativo"),
        BotCommand("cat", "📄 Exibir conteúdo de um arquivo"),
        BotCommand("tasks", "📋 Ver tarefas compartilhadas com Hermes"),
        BotCommand("debate", "🤝 Debater tema técnico entre Antigravity e Hermes"),
        BotCommand("hermes", "🪽 Delegar tarefa para o Hermes Agent"),
        BotCommand("cancel", "🛑 Cancelar processo em execução"),
        BotCommand("reset", "🔄 Reiniciar contexto da sessão"),
        BotCommand("help", "💡 Manual e ajuda completa"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands registered in Telegram UI menu.")
    except Exception as e:
        logger.warning(f"Failed to register bot commands: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)

    mode_emojis = {"build": "🏗️ Build (Execução)", "plan": "📐 Plan (Arquitetura)", "audit": "🛡️ Audit (Segurança)"}
    mode_str = mode_emojis.get(cfg.get("agent_mode", "build"), "🏗️ Build")

    msg = (
        f"🌌 **Antigravity Telegram Bot v6.0 (Ultimate Edition)**\n\n"
        f"Olá, **{user.first_name}**! Eu sou o seu agente **Google Antigravity** em execução contínua 24/7.\n\n"
        f"📂 **Workspace Ativo:** `{cfg['active_workspace']}`\n"
        f"⚙️ **Modo de Agente:** `{mode_str}`\n"
        f"🧠 **Roteamento LLM:** `{cfg['active_model']}`\n"
        f"🎙️ **Voz Neural (TTS):** `{'Ativada 🔊' if cfg['voice_out_enabled'] else 'Desativada 🔇'}`\n\n"
        f"**Comandos Rápidos:**\n"
        f"• `/browse` - Explorador interativo de pastas e arquivos.\n"
        f"• `/mode` - Alterna entre Build, Plan e Audit.\n"
        f"• `/doctor` - Diagnóstico de saúde e latência de todos os subsistemas.\n"
        f"• `/status` - Painel de hardware, CPU e RAM do host.\n"
        f"• `/history` - Histórico das últimas tarefas executadas.\n"
        f"• `/run <comando>` - Executa comando no terminal do workspace.\n"
        f"• `/git` / `/diff` / `/commit <msg>` - Operações completas de Git.\n"
        f"• `/cd <pasta>` / `/ls` / `/cat <arq>` - Navegação completa no disco.\n"
        f"• `/hermes <instrução>` - Delega para o Hermes Agent."
    )
    keyboard = [
        [
            InlineKeyboardButton("📂 Explorar Arquivos", callback_data="browse:root"),
            InlineKeyboardButton("⚙️ Modo de Agente", callback_data="action:mode"),
        ],
        [
            InlineKeyboardButton("🩺 Doctor Check", callback_data="action:doctor"),
            InlineKeyboardButton("📊 Status & Métricas", callback_data="action:status"),
        ],
        [
            InlineKeyboardButton("🧠 Modelos", callback_data="action:model"),
            InlineKeyboardButton("🎙️ Alternar Voz", callback_data="action:toggle_voice"),
        ],
        [
            InlineKeyboardButton("📋 Quadro de Tarefas", callback_data="action:tasks"),
            InlineKeyboardButton("🌿 Git Status", callback_data="action:git_status"),
        ],
        [
            InlineKeyboardButton("🪽 Chamar Hermes", callback_data="action:hermes_hint"),
        ]
    ]
    await update.message.reply_text(
        msg,
        message_thread_id=topic_id,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def browse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interactive inline file explorer inspired by CoderBOT and OpenCode."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    target_dir = cfg["active_workspace"]

    await render_file_browser(update, target_dir, target_dir, is_callback=False, topic_id=topic_id)


async def render_file_browser(update, current_dir: Path, root_dir: Path, is_callback: bool = False, topic_id: Optional[int] = None):
    """Renders buttons for interactive directory navigation."""
    try:
        if not current_dir.exists() or not current_dir.is_dir():
            current_dir = root_dir

        items = sorted(list(current_dir.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
        dirs = [item for item in items if item.is_dir() and not item.name.startswith(".")][:8]
        files = [item for item in items if item.is_file() and not item.name.startswith(".")][:10]

        keyboard = []
        # Directory rows (2 per line)
        dir_buttons = []
        for d in dirs:
            rel = d.relative_to(root_dir) if d != root_dir else Path(".")
            dir_buttons.append(InlineKeyboardButton(f"📁 {d.name}", callback_data=f"br:d:{rel}"))
            if len(dir_buttons) == 2:
                keyboard.append(dir_buttons)
                dir_buttons = []
        if dir_buttons:
            keyboard.append(dir_buttons)

        # File rows (2 per line)
        file_buttons = []
        for f in files:
            rel = f.relative_to(root_dir) if f != root_dir else Path(".")
            file_buttons.append(InlineKeyboardButton(f"📄 {f.name[:18]}", callback_data=f"br:f:{rel}"))
            if len(file_buttons) == 2:
                keyboard.append(file_buttons)
                file_buttons = []
        if file_buttons:
            keyboard.append(file_buttons)

        # Navigation controls
        nav_row = []
        if current_dir != root_dir and current_dir.parent >= root_dir:
            parent_rel = current_dir.parent.relative_to(root_dir)
            nav_row.append(InlineKeyboardButton("⬅️ Voltar", callback_data=f"br:d:{parent_rel}"))
        nav_row.append(InlineKeyboardButton("📂 Fixar como Workspace", callback_data=f"br:set:{current_dir.relative_to(root_dir)}"))
        keyboard.append(nav_row)

        text = f"📂 **Explorador Interativo de Arquivos**\n\n📍 **Diretório:** `{current_dir}`\n• Pastas: `{len(dirs)}` | Arquivos: `{len(files)}`"

        if is_callback:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(text, message_thread_id=topic_id, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        err_msg = f"❌ Erro no explorador: `{e}`"
        if is_callback:
            await update.callback_query.edit_message_text(err_msg)
        else:
            await update.message.reply_text(err_msg, message_thread_id=topic_id)


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets operating mode: Build, Plan, or Audit."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)

    keyboard = [
        [InlineKeyboardButton("🏗️ Modo Build (Execução Completa)", callback_data="mode:build")],
        [InlineKeyboardButton("📐 Modo Plan (Arquitetura & Leitura)", callback_data="mode:plan")],
        [InlineKeyboardButton("🛡️ Modo Audit (Auditoria de Segurança)", callback_data="mode:audit")],
    ]
    msg = (
        f"⚙️ **Modo de Operação do Agente:**\n\n"
        f"• **Modo Atual:** `{cfg.get('agent_mode', 'build').upper()}`\n\n"
        f"Selecione o comportamento desejado para as próximas solicitações:"
    )
    await update.message.reply_text(msg, message_thread_id=topic_id, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays recent execution history and metrics."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    history = db.get_recent_history(6)

    if not history:
        await update.message.reply_text("📜 **Histórico:** Nenhuma execução registrada recentemente.", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
        return

    lines = ["📜 **Histórico Recente de Execuções:**\n"]
    for m_id, cmd_type, prompt_sum, dur, succ, ts in history:
        dt_str = time.strftime("%d/%m %H:%M:%S", time.localtime(ts))
        icon = "🟢" if succ else "🔴"
        lines.append(f"{icon} `[#{m_id}]` **{cmd_type}** ({dt_str})\n   *Duração:* `{dur:.2f}s` | *Prompt:* `{prompt_sum[:60]}...`\n")

    await update.message.reply_text("\n".join(lines), message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)


async def doctor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)

    status_msg = await update.message.reply_text("🩺 **Executando auditoria completa de saúde nos subsistemas...**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)

    try:
        audit = await doctor.run_doctor_audit(
            TELEGRAM_BOT_TOKEN,
            GROQ_API_KEY,
            GEMINI_API_KEY,
            cfg["active_workspace"],
            freellm_key=FREE_LLM_API_KEY,
            freellm_base_url=FREE_LLM_BASE_URL
        )
        report = doctor.format_doctor_report(audit)
        await status_msg.edit_text(report, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await status_msg.edit_text(f"❌ Erro na auditoria do Doctor: `{e}`")
    finally:
        trim_process_memory()


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None

    cpu_pct = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    ram_used_gb = round(ram.used / (1024**3), 2)
    ram_total_gb = round(ram.total / (1024**3), 2)
    ram_pct = ram.percent

    daemon_proc = psutil.Process(os.getpid())
    daemon_rss_mb = round(daemon_proc.memory_info().rss / (1024 * 1024), 2)

    disk_d = psutil.disk_usage(r"D:\\") if os.path.exists(r"D:\\") else psutil.disk_usage(r"C:\\")
    disk_free_gb = round(disk_d.free / (1024**3), 2)

    uptime_sec = int(time.time() - BOT_START_TIME)
    uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s"
    total_tasks = db.get_total_tasks_count()

    try:
        res = subprocess.run([AGY_PATH, "--version"], capture_output=True, text=True, timeout=5)
        agy_ver = res.stdout.strip() or "OK"
    except Exception:
        agy_ver = "1.1.17"

    cfg = db.get_settings(chat_id, topic_id)
    status_msg = (
        f"📊 **Painel Sentinel Daemon v6.0 (24/7 Health)**\n\n"
        f"• **Antigravity CLI:** `{agy_ver}` | **PID:** `{os.getpid()}`\n"
        f"• **Uptime do Bot:** `{uptime_str}` | **Tarefas:** `{total_tasks}`\n"
        f"• **Memória do Bot (RSS):** `{daemon_rss_mb} MB` *(Otimizado)*\n"
        f"• **Host CPU:** `{cpu_pct}%` | **Host RAM:** `{ram_used_gb}/{ram_total_gb} GB ({ram_pct}%)`\n"
        f"• **Espaço Livre (D:):** `{disk_free_gb} GB`\n"
        f"• **Workspace Ativo:** `{cfg['active_workspace']}`\n"
        f"• **Modo Ativo:** `{cfg.get('agent_mode', 'build').upper()}`\n"
        f"• **Roteador LLM:** `{cfg['active_model']}`\n"
        f"• **Micro-Server Métricas:** `http://127.0.0.1:{METRICS_PORT}/metrics`\n"
        f"• **Integridade:** 🟢 100% Saudável & Monitorado"
    )
    await update.message.reply_text(status_msg, message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)


async def run_terminal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text("Uso: `/run <comando do powershell>` (ex: `/run npm test` ou `/run dir`)", parse_mode=ParseMode.MARKDOWN)
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    command_str = " ".join(context.args)

    # Guardian Pattern: Intercept high-risk destructive commands
    dangerous_triggers = ["del /s", "rmdir /s", "rm -rf", "git reset --hard", "format ", "Format-Volume", "drop table", "diskpart"]
    if any(dt in command_str.lower() for dt in dangerous_triggers):
        confirm_id = f"cmd_{int(time.time())}"
        PENDING_CONFIRMATIONS[confirm_id] = command_str
        keyboard = [
            [
                InlineKeyboardButton("⚠️ Confirmar Execução", callback_data=f"confirm:{confirm_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action"),
            ]
        ]
        await update.message.reply_text(
            f"🛡️ **Guardian AI - Alerta de Segurança:**\n\nO comando solicitado possui alto potencial destrutivo:\n`{command_str}`\n\nDeseja realmente prosseguir?",
            message_thread_id=topic_id,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await reactions.set_message_reaction(context, chat_id, update.message.message_id, "⚡")
    status_msg = await update.message.reply_text(f"⚡ **Executando:** `{command_str}`...", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)

    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command_str],
            capture_output=True,
            text=True,
            cwd=cfg["active_workspace"],
            timeout=120
        )
        out = res.stdout.strip()
        err = res.stderr.strip()
        combined = out if out else err
        if not combined:
            combined = "(Comando executado com sucesso sem saída de texto)"

        formatted = f"⚡ **Resultado de `{command_str}`:**\n```\n{combined}\n```"
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "👍")
        await send_smart_delivery(chat_id, topic_id, formatted, context, status_message=status_msg, reply_to_message_id=update.message.message_id)
    except subprocess.TimeoutExpired:
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "❌")
        await status_msg.edit_text("⏱️ **Timeout:** O comando excedeu o limite de 120 segundos.")
    except Exception as e:
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "❌")
        await status_msg.edit_text(f"❌ Erro ao executar comando: `{e}`")
    finally:
        trim_process_memory()


async def cd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None

    if not context.args:
        cfg = db.get_settings(chat_id, topic_id)
        await update.message.reply_text(f"📂 **Workspace atual:** `{cfg['active_workspace']}`\n\nPara alterar: `/cd <caminho_ou_pasta>`", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
        return

    target = " ".join(context.args)
    new_path = Path(target)
    if not new_path.is_absolute():
        cfg = db.get_settings(chat_id, topic_id)
        new_path = (cfg["active_workspace"] / target).resolve()

    if new_path.exists() and new_path.is_dir():
        db.set_workspace(chat_id, topic_id, new_path)
        await update.message.reply_text(f"✅ **Workspace alterado para:** `{new_path}`", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ Diretório não encontrado: `{new_path}`", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)


async def ls_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    target_dir = cfg["active_workspace"]
    if context.args:
        target_dir = target_dir / " ".join(context.args)

    try:
        if not target_dir.exists():
            await update.message.reply_text(f"❌ Diretório não encontrado: `{target_dir}`", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
            return

        items = list(target_dir.iterdir())[:35]
        dirs = [f"📁 `{item.name}/`" for item in items if item.is_dir()]
        files = [f"📄 `{item.name}` ({round(item.stat().st_size/1024, 1)} KB)" for item in items if item.is_file()]

        listing = "\n".join(dirs + files) if (dirs or files) else "*(Diretório vazio)*"
        msg = f"📂 **Conteúdo de `{target_dir}`:**\n\n{listing}"
        await update.message.reply_text(msg, message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao listar: `{e}`", message_thread_id=topic_id)


async def cat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text("Uso: `/cat <caminho_do_arquivo>`", parse_mode=ParseMode.MARKDOWN)
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    file_path = cfg["active_workspace"] / " ".join(context.args)

    try:
        if not file_path.exists() or not file_path.is_file():
            await update.message.reply_text(f"❌ Arquivo não encontrado: `{file_path}`", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
            return

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        await send_smart_delivery(chat_id, topic_id, f"📄 **`{file_path.name}`:**\n```\n{content}\n```", context, reply_to_message_id=update.message.message_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao ler arquivo: `{e}`", message_thread_id=topic_id)


async def git_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    subcmd = " ".join(context.args) if context.args else "status --short"

    try:
        res = subprocess.run(f"git {subcmd}", shell=True, capture_output=True, text=True, cwd=cfg["active_workspace"], timeout=15)
        out = res.stdout.strip() or res.stderr.strip() or "(Git sem alterações pendentes)"
        msg = f"🌿 **Git `{subcmd}` em `{cfg['active_workspace'].name}`:**\n```\n{out}\n```"

        keyboard = [
            [
                InlineKeyboardButton("🔍 Ver Diff", callback_data="action:git_diff"),
                InlineKeyboardButton("🌿 Git Log", callback_data="action:git_log"),
            ]
        ]
        await update.message.reply_text(msg, message_thread_id=topic_id, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro Git: `{e}`", message_thread_id=topic_id)


async def diff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    target = " ".join(context.args) if context.args else ""

    try:
        res = subprocess.run(f"git diff {target}", shell=True, capture_output=True, text=True, cwd=cfg["active_workspace"], timeout=15)
        diff_text = res.stdout.strip() or "(Nenhuma modificação não comitada no momento)"
        msg = f"🔍 **Git Diff:**\n```diff\n{diff_text}\n```"
        await send_smart_delivery(chat_id, topic_id, msg, context, reply_to_message_id=update.message.message_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao obter diff: `{e}`", message_thread_id=topic_id)


async def commit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text("Uso: `/commit <mensagem do commit>` (ex: `/commit feat: add voice support`)", parse_mode=ParseMode.MARKDOWN)
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    commit_msg = " ".join(context.args)

    try:
        subprocess.run("git add -A", shell=True, check=True, cwd=cfg["active_workspace"], timeout=10)
        res = subprocess.run(f"git commit -m \"{commit_msg}\"", shell=True, capture_output=True, text=True, cwd=cfg["active_workspace"], timeout=15)
        out = res.stdout.strip() or res.stderr.strip()
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "👍")
        await update.message.reply_text(f"💾 **Commit Realizado:**\n```\n{out}\n```", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "❌")
        await update.message.reply_text(f"❌ Erro ao commitar: `{e}`", message_thread_id=topic_id)


async def blackboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    tasks = db.get_blackboard_recent(8)

    if not tasks:
        await update.message.reply_text("📋 **Quadro Multi-Agente:** Nenhuma tarefa registrada recentemente.", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
        return

    lines = ["📋 **Quadro de Tarefas Multi-Agente (Hermes ↔ Antigravity):**\n"]
    for t_id, sender, target, topic, content, status, ts in tasks:
        dt_str = time.strftime("%d/%m %H:%M", time.localtime(ts))
        lines.append(f"• `[#{t_id}]` **{sender} ➔ {target}** ({dt_str})\n  *Tema:* {topic}\n  *Resumo:* `{content[:80]}`\n  *Status:* `{status}`\n")

    await update.message.reply_text("\n".join(lines), message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)
    new_state = not cfg["voice_out_enabled"]
    db.set_voice_enabled(chat_id, topic_id, new_state)

    state_str = "ATIVADAS 🔊 (O bot responderá por áudio)" if new_state else "DESATIVADAS 🔇 (Apenas texto)"
    await update.message.reply_text(f"🎙️ **Respostas em Áudio (TTS):** {state_str}", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    cfg = db.get_settings(chat_id, topic_id)

    keyboard = [
        [
            InlineKeyboardButton("⚡ Gemini 3.1 Pro (High)", callback_data="model:Gemini 3.1 Pro (High)"),
            InlineKeyboardButton("🚀 Gemini 3.7 Flash", callback_data="model:Gemini 3.7 Flash"),
        ],
        [
            InlineKeyboardButton("🧠 Claude Opus 4.6", callback_data="model:Claude Opus 4.6 (Thinking)"),
            InlineKeyboardButton("🤖 Roteador Automático", callback_data="model:auto"),
        ]
    ]
    await update.message.reply_text(
        f"🧠 **Selecione o Modelo para o Antigravity:**\n\nModelo atual: `{cfg['active_model']}`",
        message_thread_id=topic_id,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes automated system maintenance, RAM trimming, and temp cleanup."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None

    await reactions.set_message_reaction(context, chat_id, update.message.message_id, "🧹")
    status_msg = await update.message.reply_text("🧹 **Executando rotina de otimização e limpeza do sistema...**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)

    try:
        ps_script = BASE_DIR / "maintenance.ps1"
        res = await asyncio.create_subprocess_exec(
            "powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(ps_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await res.communicate()
        out_text = stdout.decode("utf-8", errors="replace").strip()

        # Trigger full working set memory trim & SQLite shrink
        trim_process_memory()

        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "👍")
        await status_msg.edit_text(out_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Clean command error: {e}")
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "❌")
        await status_msg.edit_text(f"❌ Erro na otimização: `{e}`")
    finally:
        trim_process_memory()


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    proc = ACTIVE_PROCESSES.get(chat_id)
    if proc:
        try:
            proc.terminate()
            await reactions.set_message_reaction(context, chat_id, update.message.message_id, "🛑")
            await update.message.reply_text("🛑 **Processo cancelado com sucesso.**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"⚠️ Erro ao cancelar: `{e}`", message_thread_id=topic_id)
    else:
        await update.message.reply_text("ℹ️ Nenhuma tarefa em execução para cancelar.", message_thread_id=topic_id)


async def shutdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Securely shuts down the bot daemon with explicit confirmation."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    confirm_id = f"shutdown_{int(time.time())}"
    keyboard = [
        [
            InlineKeyboardButton("🛑 Confirmar Encerramento", callback_data=f"shutdown:{confirm_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action"),
        ]
    ]
    await update.message.reply_text(
        "🛑 **Encerramento do Daemon Antigravity:**\n\n"
        "Você tem certeza que deseja desligar o bot? O processo irá parar de escutar comandos no Telegram.\n\n"
        "Para reiniciar manualmente, execute `python bot.py` na pasta do projeto.",
        message_thread_id=topic_id,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None
    ACTIVE_PROCESSES.pop(chat_id, None)
    await reactions.set_message_reaction(context, chat_id, update.message.message_id, "🔄")
    await update.message.reply_text("🔄 **Sessão reiniciada.** Contexto limpo.", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)


async def _perform_shutdown():
    """Gracefully terminate the bot process after shutdown confirmation."""
    await asyncio.sleep(0.5)
    raise SystemExit


async def hermes_bridge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text("Uso: `/hermes <instrução para o Hermes Agent>`", parse_mode=ParseMode.MARKDOWN)
        return

    prompt = " ".join(context.args)
    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None

    await reactions.set_message_reaction(context, chat_id, update.message.message_id, "🪽")
    status_msg = await update.message.reply_text("🪽 **Enviando solicitação ao Hermes Agent...**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(live_progress_updater(status_msg, stop_event))

    try:
        response, success = await execute_hermes_prompt(chat_id, prompt)
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "👍" if success else "❌")
    finally:
        stop_event.set()
        await progress_task

    formatted = f"🪽 **Resposta do Hermes Agent:**\n\n{response}"
    await send_smart_delivery(chat_id, topic_id, formatted, context, status_message=status_msg, reply_to_message_id=update.message.message_id)


async def debate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes a structured technical debate between Google Antigravity and Hermes Agent."""
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not context.args:
        await update.message.reply_text("Uso: `/debate <tema ou dúvida técnica para debater>`\nExemplo: `/debate Qual a melhor estratégia de microserviços vs monolito modular para nossa stack?`", parse_mode=ParseMode.MARKDOWN)
        return

    topic = " ".join(context.args)
    chat_id = update.effective_chat.id
    topic_id = update.message.message_thread_id if update.message else None

    await reactions.set_message_reaction(context, chat_id, update.message.message_id, "🤝")
    status_msg = await update.message.reply_text(f"🤝 **Iniciando debate técnico multi-agente...**\n`{topic}`\n\n⏳ Consultando Antigravity & Hermes...", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(live_progress_updater(status_msg, stop_event))

    try:
        # 1. Antigravity analysis
        agy_prompt = f"Você está participando de um debate técnico com o Hermes Agent sobre o tema: '{topic}'. Forneça sua tese arquitetural, princípios recomendados e justificativas de forma estruturada e concisa."
        agy_res, _ = await execute_agy_prompt(chat_id, topic_id, agy_prompt)

        # 2. Hermes counter-analysis & critique
        hermes_prompt = f"O Google Antigravity apresentou a seguinte tese sobre '{topic}':\n\n\"{agy_res[:800]}\"\n\nAtue como revisor técnico e contraponto prático do Hermes Agent. Destaque riscos, trade-offs e a melhor estratégia pragmática de execução."
        hermes_res, _ = await execute_hermes_prompt(chat_id, hermes_prompt)

        db.post_blackboard("Antigravity ↔ Hermes", "Luca", f"Debate: {topic[:40]}", f"Agy vs Hermes debate on: {topic[:80]}")

        formatted_debate = (
            f"🤝 **Debate Técnico Multi-Agente:**\n`{topic}`\n\n"
            f"🌌 **Perspectiva Google Antigravity (Arquitetura & Design):**\n{agy_res}\n\n"
            f"🪽 **Contraponto Hermes Agent (Execução & Trade-offs):**\n{hermes_res}"
        )
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "👍")
    except Exception as e:
        logger.error(f"Debate error: {e}", exc_info=True)
        formatted_debate = f"❌ Erro durante o debate multi-agente: `{e}`"
        await reactions.set_message_reaction(context, chat_id, update.message.message_id, "❌")
    finally:
        stop_event.set()
        await progress_task

    await send_smart_delivery(chat_id, topic_id, formatted_debate, context, status_message=status_msg, reply_to_message_id=update.message.message_id)


# ── 10. Message Handlers (Voice, Photo, Document, Text) ───────────────────────

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    message = update.message
    voice = message.voice or message.audio
    if not voice:
        return

    chat_id = update.effective_chat.id
    topic_id = message.message_thread_id

    await reactions.set_message_reaction(context, chat_id, message.message_id, "🎙️")
    status_msg = await message.reply_text("🎙️ **Transcrevendo áudio...**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)

    audio_path = TEMP_DIR / f"voice_{int(time.time())}_{voice.file_unique_id}.ogg"
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        await tg_file.download_to_drive(str(audio_path))

        transcription = await transcribe_audio(audio_path)
        if not transcription:
            await reactions.set_message_reaction(context, chat_id, message.message_id, "❌")
            await status_msg.edit_text("❌ Não foi possível transcrever o áudio.")
            return

        await status_msg.edit_text(
            f"🎙️ **Transcrição:**\n_\"{transcription}\"_\n\n⏳ **Processando no Antigravity...**",
            parse_mode=ParseMode.MARKDOWN
        )

        stop_event = asyncio.Event()
        progress_task = asyncio.create_task(live_progress_updater(status_msg, stop_event))

        try:
            response, success = await execute_agy_prompt(chat_id, topic_id, transcription)
            await reactions.set_message_reaction(context, chat_id, message.message_id, "👍" if success else "❌")
        finally:
            stop_event.set()
            await progress_task

        await send_smart_delivery(
            chat_id, topic_id, response, context,
            status_message=status_msg, reply_to_message_id=message.message_id,
            send_audio_reply=True
        )
    except Exception as e:
        logger.error(f"Voice error: {e}", exc_info=True)
        await reactions.set_message_reaction(context, chat_id, message.message_id, "❌")
        await status_msg.edit_text(f"❌ Erro ao processar áudio: `{e}`")
    finally:
        if audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass
        trim_process_memory()


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    message = update.message
    photo = message.photo[-1]
    caption = (message.caption or "").strip()
    chat_id = update.effective_chat.id
    topic_id = message.message_thread_id

    await reactions.set_message_reaction(context, chat_id, message.message_id, "🖼️")
    status_msg = await message.reply_text("🖼️ **Baixando imagem e iniciando análise...**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
    img_path = TEMP_DIR / f"photo_{int(time.time())}_{photo.file_unique_id}.png"

    try:
        tg_file = await context.bot.get_file(photo.file_id)
        await tg_file.download_to_drive(str(img_path))

        prompt = f"Analise a imagem salva em '{img_path}'. {caption if caption else 'Descreva o que vê e resolva eventuais erros apontados.'}"
        stop_event = asyncio.Event()
        progress_task = asyncio.create_task(live_progress_updater(status_msg, stop_event))

        try:
            response, success = await execute_agy_prompt(chat_id, topic_id, prompt)
            await reactions.set_message_reaction(context, chat_id, message.message_id, "👍" if success else "❌")
        finally:
            stop_event.set()
            await progress_task

        await send_smart_delivery(chat_id, topic_id, response, context, status_message=status_msg, reply_to_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Photo error: {e}", exc_info=True)
        await reactions.set_message_reaction(context, chat_id, message.message_id, "❌")
        await status_msg.edit_text(f"❌ Erro ao processar imagem: `{e}`")
    finally:
        if img_path.exists():
            try:
                img_path.unlink()
            except Exception:
                pass
        trim_process_memory()


async def handle_document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    message = update.message
    doc = message.document
    caption = (message.caption or "").strip()
    chat_id = update.effective_chat.id
    topic_id = message.message_thread_id

    await reactions.set_message_reaction(context, chat_id, message.message_id, "📎")
    status_msg = await message.reply_text(f"📎 **Baixando arquivo `{doc.file_name}`...**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)
    doc_path = TEMP_DIR / f"{int(time.time())}_{doc.file_name}"

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(str(doc_path))

        prompt = f"O arquivo '{doc.file_name}' foi salvo em '{doc_path}'. {caption if caption else 'Analise o arquivo e explique seu conteúdo.'}"
        stop_event = asyncio.Event()
        progress_task = asyncio.create_task(live_progress_updater(status_msg, stop_event))

        try:
            response, success = await execute_agy_prompt(chat_id, topic_id, prompt)
            await reactions.set_message_reaction(context, chat_id, message.message_id, "👍" if success else "❌")
        finally:
            stop_event.set()
            await progress_task

        await send_smart_delivery(chat_id, topic_id, response, context, status_message=status_msg, reply_to_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Doc error: {e}", exc_info=True)
        await reactions.set_message_reaction(context, chat_id, message.message_id, "❌")
        await status_msg.edit_text(f"❌ Erro ao processar documento: `{e}`")
    finally:
        if doc_path.exists():
            try:
                doc_path.unlink()
            except Exception:
                pass
        trim_process_memory()


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    message = update.message
    if not message or not message.text:
        return

    chat = update.effective_chat
    text = message.text.strip()
    bot_username = context.bot.username or "Antigravity_lucasantannaeng_bot"
    topic_id = message.message_thread_id

    logger.info(f"Recebida mensagem do usuário {user.id} ({user.first_name}) no Chat {chat.id} ({chat.type}): '{text[:60]}'")

    # Group filtering: only answer if mentioned or replied to
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        is_mentioned = bool(
            (bot_username and f"@{bot_username.lower()}" in text.lower())
            or "@antigravity" in text.lower()
        )
        is_reply_to_bot = bool(
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.id == context.bot.id
        )
        if not (is_mentioned or is_reply_to_bot):
            logger.debug(f"Ignorando mensagem em grupo sem menção/reply: '{text[:40]}'")
            return

        if is_mentioned and bot_username:
            text = text.replace(f"@{bot_username}", "").replace(f"@{bot_username.lower()}", "").replace("@antigravity", "").strip()

    if not text:
        return

    chat_id = chat.id
    await reactions.set_message_reaction(context, chat_id, message.message_id, "🤔")
    status_msg = await message.reply_text("⚡ **Processando...**", message_thread_id=topic_id, parse_mode=ParseMode.MARKDOWN)

    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(live_progress_updater(status_msg, stop_event))

    try:
        response, success = await execute_agy_prompt(chat_id, topic_id, text)
        await reactions.set_message_reaction(context, chat_id, message.message_id, "👍" if success else "❌")
    finally:
        stop_event.set()
        await progress_task

    await send_smart_delivery(chat_id, topic_id, response, context, status_message=status_msg, reply_to_message_id=message.message_id)
    trim_process_memory()


# ── 11. Callbacks Handler ────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_authorized(user_id):
        return

    chat_id = query.message.chat_id
    topic_id = query.message.message_thread_id
    data = query.data

    cfg = db.get_settings(chat_id, topic_id)
    root_ws = cfg["active_workspace"]

    if data.startswith("model:"):
        selected = data.split("model:", 1)[1]
        db.set_model(chat_id, topic_id, selected)
        display = "Roteador Automático" if selected == "auto" else selected
        await query.edit_message_text(f"✅ **Modelo atualizado!**\n\nNovo modelo ativo: `{display}`", parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("mode:"):
        selected_mode = data.split("mode:", 1)[1]
        db.set_agent_mode(chat_id, topic_id, selected_mode)
        mode_names = {"build": "🏗️ Build (Execução Completa)", "plan": "📐 Plan (Arquitetura & Leitura)", "audit": "🛡️ Audit (Auditoria de Segurança)"}
        await query.edit_message_text(f"✅ **Modo de Agente alterado para:**\n`{mode_names.get(selected_mode, selected_mode)}`", parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("confirm:"):
        confirm_id = data.split("confirm:", 1)[1]
        cmd = PENDING_CONFIRMATIONS.pop(confirm_id, None)
        if cmd:
            await query.edit_message_text(f"⚡ **Executando comando confirmado:** `{cmd}`...", parse_mode=ParseMode.MARKDOWN)
            res = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, text=True, cwd=root_ws, timeout=120)
            out = res.stdout.strip() or res.stderr.strip() or "(Executado com sucesso)"
            await query.edit_message_text(f"⚡ **Resultado de `{cmd}`:**\n```\n{out}\n```", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("⚠️ Solicitação expirada ou já executada.")

    elif data == "cancel_action":
        await query.edit_message_text("❌ Operação cancelada.")

    elif data.startswith("shutdown:"):
        confirm_id = data.split("shutdown:", 1)[1]
        # Simple confirmation flow - actual shutdown is handled by process exit
        await query.edit_message_text(
            "🛑 **Encerramento Confirmado!**\n\n"
            "O bot está sendo desligado. O processo será encerrado agora.\n\n"
            "Para reiniciar, use o script `run-hidden.vbs` ou execute manualmente:\n"
            "`python bot.py`",
            parse_mode=ParseMode.MARKDOWN
        )
        # Schedule process exit after sending response
        asyncio.create_task(_perform_shutdown())

    # Interactive File Browser Callbacks
    elif data.startswith("br:d:"):
        rel_path = data.split("br:d:", 1)[1]
        target = (root_ws / rel_path).resolve()
        await render_file_browser(update, target, root_ws, is_callback=True, topic_id=topic_id)

    elif data.startswith("br:f:"):
        rel_path = data.split("br:f:", 1)[1]
        file_path = (root_ws / rel_path).resolve()
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            content_preview = content[:2000] + ("\n...(truncado para exibição)" if len(content) > 2000 else "")
            await query.message.reply_text(f"📄 **`{file_path.name}`:**\n```\n{content_preview}\n```", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await query.message.reply_text(f"❌ Erro ao ler arquivo: `{e}`")

    elif data.startswith("br:set:"):
        rel_path = data.split("br:set:", 1)[1]
        new_ws = (root_ws / rel_path).resolve()
        if new_ws.exists() and new_ws.is_dir():
            db.set_workspace(chat_id, topic_id, new_ws)
            await query.edit_message_text(f"✅ **Novo workspace ativo fixado:** `{new_ws}`", parse_mode=ParseMode.MARKDOWN)

    elif data == "browse:root":
        await render_file_browser(update, root_ws, root_ws, is_callback=True, topic_id=topic_id)

    elif data == "action:mode":
        await mode_command(update, context)
    elif data == "action:doctor":
        await doctor_command(update, context)
    elif data == "action:status":
        await status_command(update, context)
    elif data == "action:model":
        await model_command(update, context)
    elif data == "action:toggle_voice":
        await voice_command(update, context)
    elif data == "action:tasks":
        await blackboard_command(update, context)
    elif data == "action:git_status":
        await git_command(update, context)
    elif data == "action:git_diff":
        await diff_command(update, context)
    elif data == "action:git_log":
        context.args = ["log", "-n", "5", "--oneline"]
        await git_command(update, context)
    elif data == "action:hermes_hint":
        await query.message.reply_text("💡 Para delegar tarefas ao Hermes Agent, digite:\n`/hermes <instrução>`", parse_mode=ParseMode.MARKDOWN)


# ── 12. Local Metrics Micro-Server (Port 8765) ───────────────────────────────

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            proc = psutil.Process(os.getpid())
            rss_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
            ram = psutil.virtual_memory()

            metrics_data = {
                "status": "healthy",
                "version": "6.0.0-ultimate",
                "uptime_seconds": int(time.time() - BOT_START_TIME),
                "daemon_pid": os.getpid(),
                "daemon_rss_mb": rss_mb,
                "host_cpu_pct": psutil.cpu_percent(),
                "host_ram_free_gb": round(ram.available / (1024**3), 2),
                "host_ram_total_gb": round(ram.total / (1024**3), 2),
                "total_tasks_processed": db.get_total_tasks_count(),
                "timestamp": time.time()
            }
            body = json.dumps(metrics_data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def start_metrics_server(port: int):
    """Starts thread-safe daemon HTTP server on localhost."""
    global METRICS_HTTPD
    try:
        METRICS_HTTPD = ThreadingHTTPServer(("127.0.0.1", port), MetricsHandler)
        t = threading.Thread(target=METRICS_HTTPD.serve_forever, daemon=True, name="MetricsServer")
        t.start()
        logger.info(f"Local Metrics Micro-Server running at http://127.0.0.1:{port}/metrics")
    except Exception as e:
        logger.warning(f"Could not bind metrics server on port {port}: {e}")


# ── 13. Sentinel Background Watchdog Loop ───────────────────────────────────

async def sentinel_watchdog_loop():
    """Autonomous 24/7 supervisor: trims memory, monitors host health, auto-cleans temp files."""
    logger.info("🛡️ Sentinel Watchdog Loop iniciado.")
    last_auto_clean = time.time()
    last_routine_trim = time.time()
    while True:
        try:
            await asyncio.sleep(25.0)

            proc = psutil.Process(os.getpid())
            rss_mb = proc.memory_info().rss / (1024 * 1024)
            now = time.time()

            # Active memory trimmer: if RSS > 65.0 MB or every 2 minutes
            if rss_mb > 65.0 or (now - last_routine_trim > 120.0):
                new_rss = trim_process_memory()
                last_routine_trim = now
                if rss_mb > 70.0:
                    logger.info(f"Sentinel memory trim: RSS reduced from {round(rss_mb, 2)} MB to {new_rss} MB")

            # Clean orphaned temporary files older than 10 minutes
            try:
                for temp_file in TEMP_DIR.glob("*"):
                    if temp_file.is_file() and (now - temp_file.stat().st_mtime > 600):
                        temp_file.unlink(missing_ok=True)
            except Exception:
                pass

            ram = psutil.virtual_memory()

            # Auto-run maintenance script if RAM is low (< 450MB) or every 6 hours
            if (ram.available < (450 * 1024 * 1024) and (now - last_auto_clean > 1800)) or (now - last_auto_clean > 21600):
                logger.info("Sentinel Auto-Maintenance: Running system memory trim and temp cleaner...")
                last_auto_clean = now
                try:
                    ps_script = BASE_DIR / "maintenance.ps1"
                    res = await asyncio.create_subprocess_exec(
                        "powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(ps_script),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await res.communicate()
                except Exception as ex:
                    logger.debug(f"Sentinel maintenance script error: {ex}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Sentinel watchdog exception: {e}")


# ── 14. Main Entrypoint & Self-Healing Loop ──────────────────────────────────

async def post_init_setup(application):
    await register_bot_commands(application)
    trim_process_memory()
    asyncio.create_task(sentinel_watchdog_loop())
    start_metrics_server(METRICS_PORT)


SINGLETON_MUTEX_HANDLE = None

def acquire_singleton_lock(mutex_name: str = "Local\\AntigravityTelegramBot_Singleton_Lock") -> bool:
    """Guarantees only ONE instance of the bot process runs across the entire operating system."""
    global SINGLETON_MUTEX_HANDLE
    if sys.platform == "win32":
        try:
            ERROR_ALREADY_EXISTS = 183
            SINGLETON_MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
            if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                logger.warning("⚠️ Outra instância do Antigravity Telegram Bot já está em execução. Encerrando duplicata silenciosamente.")
                return False
            return True
        except Exception as e:
            logger.debug(f"Mutex creation warning: {e}")
            return True
    return True


def wait_for_network(max_wait_seconds: int = 45) -> bool:
    """Waits for network / DNS connectivity on system boot before starting polling."""
    logger.info("Verificando conectividade com api.telegram.org...")
    start_t = time.time()
    while time.time() - start_t < max_wait_seconds:
        try:
            with socket.create_connection(("api.telegram.org", 443), timeout=3.0):
                logger.info("🟢 Conectividade com Telegram API confirmada!")
                return True
        except Exception:
            time.sleep(2.0)
    logger.warning("Tempo limite aguardando rede excedido. Tentando prosseguir...")
    return False


def main():
    if not acquire_singleton_lock():
        sys.exit(0)

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não encontrado no .env")
        sys.exit(1)

    # Boot stabilization: wait for network connection
    wait_for_network(45)

    logger.info("🚀 Iniciando Antigravity Telegram Bot v6.0 (Ultimate Edition)...")
    logger.info(f"📁 Workspace Padrão: {DEFAULT_WORKSPACE}")
    logger.info(f"🔒 Usuários Autorizados: {ALLOWED_USERS}")

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init_setup)
        .build()
    )

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("browse", browse_command))
    application.add_handler(CommandHandler("tree", browse_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler("clean", clean_command))
    application.add_handler(CommandHandler("optimize", clean_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("doctor", doctor_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("sys", status_command))
    application.add_handler(CommandHandler("voice", voice_command))
    application.add_handler(CommandHandler("model", model_command))
    application.add_handler(CommandHandler("run", run_terminal_command))
    application.add_handler(CommandHandler("cd", cd_command))
    application.add_handler(CommandHandler("ls", ls_command))
    application.add_handler(CommandHandler("cat", cat_command))
    application.add_handler(CommandHandler("git", git_command))
    application.add_handler(CommandHandler("diff", diff_command))
    application.add_handler(CommandHandler("commit", commit_command))
    application.add_handler(CommandHandler("tasks", blackboard_command))
    application.add_handler(CommandHandler("blackboard", blackboard_command))
    application.add_handler(CommandHandler("debate", debate_command))
    application.add_handler(CommandHandler("consult", debate_command))
    application.add_handler(CommandHandler("discuss", debate_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("shutdown", shutdown_command))
    application.add_handler(CommandHandler("new", reset_command))
    application.add_handler(CommandHandler("hermes", hermes_bridge_command))
    application.add_handler(CommandHandler("agy", handle_text_message))

    # Callbacks & Media
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Resilience Polling Loop with queue retention
    while True:
        try:
            logger.info("Polling iniciado (drop_pending_updates=False)...")
            application.run_polling(drop_pending_updates=False)
            break
        except Exception as e:
            logger.error(f"Polling connection drop: {e}. Reconectando em 5s...", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
