"""
Antigravity Subsystem Doctor & Diagnostics Engine
Performs end-to-end health audit of all daemon components and APIs.
"""

import os
import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import psutil
import sqlite3
import subprocess
from pathlib import Path
import httpx
import edge_tts

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "state.db"


async def run_doctor_audit(bot_token: str, groq_key: str, gemini_key: str, workspace: Path, freellm_key: str = "", freellm_base_url: str = "") -> dict:
    """Executes a full diagnostic health check of all subsystems."""
    results = {}

    # 1. Telegram API Latency
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            tg_lat = round((time.time() - t0) * 1000, 1)
            results["telegram_api"] = {
                "ok": resp.status_code == 200,
                "latency_ms": tg_lat,
                "info": f"Online ({tg_lat}ms)" if resp.status_code == 200 else f"HTTP {resp.status_code}"
            }
    except Exception as e:
        results["telegram_api"] = {"ok": False, "info": f"Falha de conexão: {e}"}

    # 2. Antigravity CLI (agy)
    try:
        res = subprocess.run(["agy", "--version"], capture_output=True, text=True, timeout=4)
        agy_ver = res.stdout.strip()
        results["antigravity_cli"] = {
            "ok": res.returncode == 0 and len(agy_ver) > 0,
            "info": f"v{agy_ver}" if res.returncode == 0 else "Erro de execução"
        }
    except Exception as e:
        results["antigravity_cli"] = {"ok": False, "info": f"Binário não encontrado: {e}"}

    # 3. Hermes Agent
    try:
        res = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=4)
        hermes_ver = res.stdout.strip().split("\n")[0]
        results["hermes_agent"] = {
            "ok": res.returncode == 0 and len(hermes_ver) > 0,
            "info": hermes_ver if res.returncode == 0 else "Erro de execução"
        }
    except Exception as e:
        results["hermes_agent"] = {"ok": False, "info": f"Binário não encontrado: {e}"}

    # 4. Audio STT (Groq Whisper)
    if groq_key:
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {groq_key}"})
                groq_lat = round((time.time() - t0) * 1000, 1)
                results["stt_engine"] = {
                    "ok": resp.status_code == 200,
                    "info": f"Groq Whisper Turbo ({groq_lat}ms)" if resp.status_code == 200 else "Erro de autenticação"
                }
        except Exception as e:
            results["stt_engine"] = {"ok": False, "info": f"Erro STT: {e}"}
    else:
        results["stt_engine"] = {"ok": bool(gemini_key), "info": "Gemini Multimodal STT" if gemini_key else "Desativado"}

    # 5. Audio TTS (Edge Neural)
    t0 = time.time()
    try:
        comm = edge_tts.Communicate("OK", "pt-BR-AntonioNeural")
        test_out = BASE_DIR / "temp" / "doc_test.mp3"
        await comm.save(str(test_out))
        tts_lat = round((time.time() - t0) * 1000, 1)
        if test_out.exists():
            test_out.unlink()
        results["tts_engine"] = {"ok": True, "info": f"Edge Neural Voice ({tts_lat}ms)"}
    except Exception as e:
        results["tts_engine"] = {"ok": False, "info": f"Erro TTS: {e}"}

    # 6. SQLite State Database
    try:
        with sqlite3.connect(DB_PATH, timeout=3.0) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            db_size_kb = round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0
            results["sqlite_db"] = {
                "ok": integrity == "ok",
                "info": f"Integridade: {integrity} ({db_size_kb} KB)"
            }
    except Exception as e:
        results["sqlite_db"] = {"ok": False, "info": f"Erro BD: {e}"}

    # 7. FreeLLM Local Proxy
    f_key = freellm_key or os.getenv("FREE_LLM_API_KEY") or os.getenv("FREELLM_API_KEY", "")
    f_url = (freellm_base_url or os.getenv("FREE_LLM_BASE_URL") or os.getenv("FREELLM_BASE_URL", "http://127.0.0.1:31415/v1")).rstrip("/")
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{f_url}/models", headers={"Authorization": f"Bearer {f_key}"})
            f_lat = round((time.time() - t0) * 1000, 1)
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("data", []))
                results["freellm_proxy"] = {
                    "ok": True,
                    "latency_ms": f_lat,
                    "info": f"Online ({count} modelos, {f_lat}ms)"
                }
            else:
                results["freellm_proxy"] = {
                    "ok": False,
                    "info": f"HTTP {resp.status_code} (Chave inválida ou erro)"
                }
    except Exception as e:
        results["freellm_proxy"] = {"ok": False, "info": f"Offline ou inacessível: {e}"}

    # 8. Hardware & Host Resources
    ram = psutil.virtual_memory()
    disk_d = psutil.disk_usage(r"D:\\") if os.path.exists(r"D:\\") else psutil.disk_usage(r"C:\\")
    proc = psutil.Process(os.getpid())
    daemon_rss_mb = round(proc.memory_info().rss / (1024 * 1024), 2)

    results["resources"] = {
        "ok": ram.available > (500 * 1024 * 1024) and daemon_rss_mb < 80.0,
        "host_cpu": f"{psutil.cpu_percent()}%",
        "host_ram": f"{round(ram.used/(1024**3), 2)}/{round(ram.total/(1024**3), 2)} GB ({ram.percent}%)",
        "host_ram_free": f"{round(ram.available/(1024**3), 2)} GB livres",
        "disk_free": f"{round(disk_d.free/(1024**3), 2)} GB livres",
        "daemon_rss": f"{daemon_rss_mb} MB (<80MB limite)",
        "daemon_rss_mb": daemon_rss_mb,
        "threads": proc.num_threads()
    }

    return results


def format_doctor_report(audit: dict) -> str:
    """Formats doctor results into a clean Telegram Markdown report."""
    def _badge(ok: bool) -> str:
        return "🟢" if ok else "🔴"

    lines = ["🩺 **Relatório do Antigravity Doctor (Diagnóstico de Saúde):**\n"]
    lines.append(f"{_badge(audit['telegram_api']['ok'])} **Telegram API:** `{audit['telegram_api']['info']}`")
    lines.append(f"{_badge(audit['antigravity_cli']['ok'])} **Antigravity CLI (`agy`):** `{audit['antigravity_cli']['info']}`")
    lines.append(f"{_badge(audit['hermes_agent']['ok'])} **Hermes Agent:** `{audit['hermes_agent']['info']}`")
    if "freellm_proxy" in audit:
        lines.append(f"{_badge(audit['freellm_proxy']['ok'])} **FreeLLM Local Proxy:** `{audit['freellm_proxy']['info']}`")
    lines.append(f"{_badge(audit['stt_engine']['ok'])} **Áudio STT:** `{audit['stt_engine']['info']}`")
    lines.append(f"{_badge(audit['tts_engine']['ok'])} **Áudio TTS:** `{audit['tts_engine']['info']}`")
    lines.append(f"{_badge(audit['sqlite_db']['ok'])} **Banco SQLite:** `{audit['sqlite_db']['info']}`")

    r = audit["resources"]
    lines.append(f"\n💻 **Recursos do Host & Daemon:**")
    lines.append(f"• **Memória do Daemon (RSS):** `{r['daemon_rss']}` ({r['threads']} threads)")
    lines.append(f"• **CPU Host:** `{r['host_cpu']}` | **RAM Host:** `{r['host_ram']}`")
    lines.append(f"• **RAM Livre Host:** `{r['host_ram_free']}`")
    lines.append(f"• **Espaço em Disco:** `{r['disk_free']}`")

    all_ok = all(v["ok"] for k, v in audit.items() if isinstance(v, dict) and "ok" in v)
    lines.append(f"\n**Veredito:** {'🟢 Todos os subsistemas operacionais e saudáveis!' if all_ok else '⚠️ Alguns subsistemas requerem atenção.'}")

    return "\n".join(lines)
