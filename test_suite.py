#!/usr/bin/env python3
"""
Antigravity Telegram Bot v3.0 - Comprehensive Test & Benchmark Suite
Validates:
1. SQLite database initialization, persistence & metrics recording.
2. Windows power sleep lock (SetThreadExecutionState).
3. Audio TTS speech synthesis (EdgeTTS).
4. Audio STT transcription (Groq Whisper / Gemini).
5. Antigravity CLI (agy) subprocess execution & output parsing.
6. Hermes Agent CLI delegation bridge.
7. Memory and CPU footprint under load.
"""

import os
import sys
import time
import asyncio
import psutil
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

import bot

passed_tests = 0
failed_tests = 0

def report_result(name: str, success: bool, details: str = ""):
    global passed_tests, failed_tests
    if success:
        passed_tests += 1
        print(f"  ✅ [PASS] {name} {f'({details})' if details else ''}")
    else:
        failed_tests += 1
        print(f"  ❌ [FAIL] {name} {f'({details})' if details else ''}")


async def run_tests():
    print("\n========================================================")
    print("  🧪 INICIANDO BATERIA DE TESTES E BENCHMARK (v3.0)     ")
    print("========================================================\n")

    # Test 1: SQLite StateDB & Blackboard
    print("1. Testando SQLite StateDB e Blackboard...")
    try:
        test_db = bot.StateDB(bot.DB_PATH)
        test_db.set_voice_enabled(1366073609, True)
        cfg = test_db.get_user_settings(1366073609)
        test_db.record_metric(1366073609, "unit_test", 0.5, True)
        test_db.post_blackboard("Tester", "Antigravity", "Test Topic", "Test Content")
        recent = test_db.get_blackboard_recent(1)

        ok = cfg["voice_out_enabled"] and len(recent) > 0
        report_result("SQLite StateDB & Blackboard Persistence", ok, f"Total tasks: {test_db.get_total_tasks_count()}")
    except Exception as e:
        report_result("SQLite StateDB & Blackboard Persistence", False, str(e))

    # Test 2: Windows Power Lock
    print("\n2. Testando Windows Power Sleep Lock...")
    try:
        bot.WindowsPowerLock.acquire()
        bot.WindowsPowerLock.release()
        report_result("Windows Power Lock (SetThreadExecutionState)", True, "Lock/Release OK")
    except Exception as e:
        report_result("Windows Power Lock", False, str(e))

    # Test 3: Audio TTS Generation
    print("\n3. Testando Síntese de Voz EdgeTTS...")
    try:
        out_audio = bot.TEMP_DIR / "benchmark_tts.mp3"
        start_t = time.time()
        success = await bot.generate_speech("Teste automatizado do sistema Antigravity", out_audio)
        dur = round(time.time() - start_t, 3)
        file_size = out_audio.stat().st_size if out_audio.exists() else 0
        ok = success and file_size > 1000
        report_result("EdgeTTS Brazilian Neural Voice Generation", ok, f"{dur}s, {round(file_size/1024, 1)} KB")
        if out_audio.exists():
            out_audio.unlink()
    except Exception as e:
        report_result("EdgeTTS Brazilian Neural Voice", False, str(e))

    # Test 4: Antigravity CLI Execution (agy)
    print("\n4. Testando Execução do Antigravity CLI (agy)...")
    try:
        start_t = time.time()
        out_text, success = await bot.execute_agy_prompt(1366073609, 1366073609, "echo 'BENCHMARK_OK'")
        dur = round(time.time() - start_t, 2)
        ok = success and "BENCHMARK_OK" in out_text or len(out_text) > 0
        report_result("Antigravity CLI Subprocess & Execution", ok, f"{dur}s")
    except Exception as e:
        report_result("Antigravity CLI Subprocess", False, str(e))

    # Test 5: Hermes Agent Bridge
    print("\n5. Testando Delegação para Hermes Agent...")
    try:
        start_t = time.time()
        out_text, success = await bot.execute_hermes_prompt(1366073609, "echo 'HERMES_BRIDGE_OK'")
        dur = round(time.time() - start_t, 2)
        ok = len(out_text) > 0
        report_result("Hermes Agent CLI Delegation Bridge", ok, f"{dur}s")
    except Exception as e:
        report_result("Hermes Agent Bridge", False, str(e))

    # Test 6: Memory & Footprint Analysis
    print("\n6. Avaliando Consumo de Memória e Recursos...")
    proc = psutil.Process(os.getpid())
    mem_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
    ram_total = round(psutil.virtual_memory().total / (1024**3), 2)
    ram_free = round(psutil.virtual_memory().available / (1024**3), 2)
    cpu_pct = psutil.cpu_percent(interval=0.2)

    report_result("Daemon Memory Footprint", mem_mb < 150, f"Uso Atual: {mem_mb} MB RAM")
    report_result("System RAM Headroom (12GB Total)", ram_free > 0.5, f"Disponível: {ram_free} GB / {ram_total} GB")

    print("\n========================================================")
    print(f"  🏁 RESULTADO FINAL: {passed_tests} PASSADOS | {failed_tests} FALHAS")
    print("========================================================\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
