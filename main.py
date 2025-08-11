import argparse
import json
import os
import queue
import sys
import threading
import sounddevice
import uvicorn

from fastapi import FastAPI
from vosk import Model, SetLogLevel, KaldiRecognizer

from app.core.core import Core

# Потокобезопасный флаг блокировки микрофона
mic_blocked = threading.Event()
q = queue.Queue()

"""
    Запускает ассистента в режиме микрофона
        1. Загружает модель Vosk
        2. Читает звук с микрофона
        3. Передаёт распознанный текст в ядро Core
"""
def run_mic_mode(model_path: str, device=None, samplerate=None, filename=None):
    if not os.path.exists(model_path):
        print(f"[ОШИБКА] Модель не найдена: {model_path}")
        sys.exit(1)

    print(f"[ИНФО] Загружаю модель из {model_path}...")
    model = Model(model_path)

    if samplerate is None:
        device_info = sounddevice.query_devices(device, 'input')
        samplerate = int(device_info['default_samplerate'])
        print(f"[ИНФО] Используется частота дискретизации: {samplerate} Гц")

    dump_fn = open(filename, "wb") if filename else None

    core = Core()
    core.init_with_plugins()
    print("[ИНФО] Ассистент инициализирован, ожидание голосовых команд...")

    with sounddevice.RawInputStream(samplerate=samplerate, blocksize=8000, device=device, dtype='int16', channels=1, callback=callback):
        rec = KaldiRecognizer(model, samplerate)
        while True:
            data = q.get()
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
            if dump_fn:
                dump_fn.write(data)

"""
    Запускает ассистента в API-режиме (HTTP + WebSocket)
"""
def run_api_mode():
    print("[ИНФО] Запуск API-режима...")
    app = FastAPI()
    core = Core()
    core.fastApiApp = app
    core.init_with_plugins()
    uvicorn.run(app, host=core.api_host, port=core.api_port, log_level=core.api_log_level)

"""
    Блокирует приём звука с микрофона
"""
def block_mic():
    mic_blocked.set()

"""
    Разблокирует приём звука с микрофона
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
    Колбэк для sounddevice: получает аудио и кладёт его в очередь
"""
def callback(indata, frames, time, status):
    if status:
        print(f"[АУДИО] Статус устройства: {status}", file=sys.stderr)
    # Если микрофон НЕ заблокирован - складываем данные
    if not mic_blocked.is_set():
        q.put(bytes(indata))
    else:
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Голосовой ассистент")
    parser.add_argument('--mode', choices=['mic', 'api'], required=True, help="Режим работы: mic - с микрофона, api - запуск HTTP/WS API")
    parser.add_argument('-m', '--model', type=str, default='./app/models/vosk', help='Путь к модели Vosk (по умолчанию ./app/models/vosk)')
    parser.add_argument('-d', '--device', type=int_or_str, help='ID или название устройства микрофона')
    parser.add_argument('-r', '--samplerate', type=int, help='Частота дискретизации (например, 16000, 44100, 48000)')
    parser.add_argument('-f', '--filename', type=str, help='Сохранять входящий звук в файл (укажите путь)')
    args = parser.parse_args()
    
    SetLogLevel(-1)

    if args.model is None:
        args.model = "./app/models/vosk"

    if args.mode == 'mic':
        run_mic_mode(model_path=args.model, device=args.device, samplerate=args.samplerate, filename=args.filename)
    elif args.mode == 'api':
        run_api_mode()
