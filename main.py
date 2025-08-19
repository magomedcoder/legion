import argparse
import json
import os
import queue
import sys
import threading
import signal
import sounddevice
import uvicorn

from fastapi import FastAPI
from vosk import Model, SetLogLevel, KaldiRecognizer

from app.core.core import Core

# Блокировка микрофона во время TTS/обработки
mic_blocked = threading.Event()
# Общий флаг завершения
stop_event = threading.Event()
# Очередь PCM-чанков от callback() к основному циклу
q = queue.Queue()

SENTINEL = None

"""
    Легион в режиме микрофона:
        1. Чтение звука с микрофона
        2. Передача распознанного текста в ядро Core
"""
def run_mic_mode(device=None, samplerate=None):
    if samplerate is None:
        device_info = sounddevice.query_devices(device, 'input')
        samplerate = int(device_info['default_samplerate'])

    model_path = "./app/models/vosk"

    core = Core()
    core.init_with_extensions()

    if not os.path.exists(model_path):
        print(f"[ОШИБКА] Модель не найдена: {model_path}")
        sys.exit(1)

    model = Model(model_path)
    rec = None
    stream = None

    print("[ИНФО] Легион инициализирован, ожидание голосовых команд...")

    try:
        stream = sounddevice.RawInputStream(samplerate=samplerate, blocksize=8000, device=device, dtype='int16', channels=1, callback=callback)
        stream.start()

        rec = KaldiRecognizer(model, samplerate)
        while not stop_event.is_set():
            try:
                data = q.get(timeout=0.5)
            except queue.Empty:
                core.update_timers()
                continue

            if data is SENTINEL:
                break 

            if rec.AcceptWaveform(data):
                recognized_data = json.loads(rec.Result())
                voice_input_str = recognized_data.get("text", "")
                if voice_input_str:
                    print(f"[РАСПОЗНАНО] {voice_input_str}")
                    # Блокируем микрофон на время обработки команды/TTS
                    block_mic()
                    try:
                        core.run_input_str(voice_input_str)
                    finally:
                        # Разблокируем даже если внутри было исключение
                        unblock_mic()
            core.update_timers()

        if rec is not None:
            try:
                final_json = json.loads(rec.FinalResult())
                final_text = final_json.get("text", "")
                if final_text:
                    print(f"[ФИНАЛ] {final_text}")
                    block_mic()
                    try:
                        core.run_input_str(final_text)
                    finally:
                        unblock_mic()
            except Exception:
                pass

    finally:
        try:
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception:
            pass

        if hasattr(core, "shutdown"):
            try:
                core.shutdown()
            except Exception:
                pass

        print("[ИНФО] Завершение работы")

"""
    Легион в API-режиме (HTTP + WebSocket)
"""
def run_api_mode():
    app = FastAPI()
    core = Core()
    core.fastapi_app = app
    core.init_with_extensions()
    print("[ИНФО] Легион в API-режиме...")
    uvicorn.run(app, host=core.api_host, port=core.api_port, log_level=core.api_log_level)

def handle_signal(signum, frame):
    print("\n[ИНФО] Выключаюсь, чуть подождите...", flush=True)
    stop_event.set()
    try:
        q.put_nowait(SENTINEL)
    except queue.Full:
        pass

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

"""
    Блокировка приёма звука с микрофона
"""
def block_mic():
    mic_blocked.set()

"""
    Разблокировка приёма звука с микрофона
"""
def unblock_mic():
    mic_blocked.clear()

"""
    Преобразует строку в int, если это возможно
"""
def int_or_str(text):
    try:
        return int(text)
    except ValueError:
        return text

"""
    Колбэк получает аудио и кладёт его в очередь
"""
def callback(indata, frames, time, status):
    if status:
        print(f"[АУДИО] Статус устройства: {status}", file=sys.stderr)
    # Если микрофон НЕ заблокирован - складываем данные
    if stop_event.is_set():
        return

    if not mic_blocked.is_set():
        try:
            q.put_nowait(bytes(indata))
        except queue.Full:
            pass
    else:
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Легион")
    parser.add_argument('--mode', choices=['mic', 'api'], required=True, help="Режим работы: mic - с микрофона, api - HTTP/WS API")
    parser.add_argument('-d', '--device', type=int_or_str, help='ID или название устройства микрофона')
    parser.add_argument('-r', '--samplerate', type=int, help='Частота дискретизации (например, 16000, 44100, 48000)')
    args = parser.parse_args()

    SetLogLevel(-1)

    try:
        if args.mode == 'mic':
            run_mic_mode(device=args.device, samplerate=args.samplerate)
        elif args.mode == 'api':
            run_api_mode()
    finally:
        stop_event.set()
        try:
            q.put_nowait(SENTINEL)
        except queue.Full:
            pass
