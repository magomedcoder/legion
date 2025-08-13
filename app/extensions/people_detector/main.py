import os
import cv2
import time
import threading
from typing import Optional

from app.core.core import Core

"""
    Детектор людей

    Команды:
        включи детектор людей  - запуск фонового потока: чтение камеры и подсчёт людей
        выключи детектор людей - остановка работы
        сколько людей          - голосовой ответ с текущим числом обнаруженных людей
        включи оповещение      - голосовое уведомление при появлении людей в кадре
        выключи оповещение     - отключение голосовых уведомлений

    Опции:
        camera_source       - индекс камеры или URL (RTSP/HTTP)
        poll_ms             - периодичность обработки (мс)
        confidence          - минимальный порог уверенности детекции
        resize_width/height - размер кадра для предобработки (0 - без изменения)
        model_dir           - путь к папке с моделью
        prototxt            - .prototxt
        weights             - .caffemodel
        use_cuda            - использовать CUDA
        alert_min_interval  - минимальная пауза между голосовыми оповещениями (сек)
        start_on_load       - запуск детектора при старте расширения
"""

modname = os.path.basename(__package__)[15:]

_worker: Optional[threading.Thread] = None
_stop_evt: Optional[threading.Event] = None
_state_lock = threading.Lock()
_last_count: int = 0
_alert_enabled: bool = False
_last_alert_ts: float = 0.0

def start(core: Core):
    manifest = {
        "name": "Детектор людей",

        "options": {
            "camera_source": 0,
            "poll_ms": 400,
            "confidence": 0.5,
            "resize_width": 640,
            "resize_height": 480,
            "model_dir": "./app/models/mobilenet-ssd",
            "prototxt": "deploy.prototxt",
            "weights": "mobilenet_iter_73000.caffemodel",
            "use_cuda": False,
            "alert_min_interval": 10,
            "start_on_load": False,
        },

        "commands": {
            "включи детектор людей": _cmd_start,
            "выключи детектор людей": _cmd_stop,
            "сколько людей": _cmd_how_many,
            "включи оповещение": _cmd_alert_on,
            "выключи оповещение": _cmd_alert_off,
        },
    }

    opts = core.extension_options(modname) or {}
    if bool(opts.get("start_on_load", False)):
        try:
            _start_worker(core)
        except Exception:
            pass

    return manifest

def _cmd_start(core: Core, phrase: str):
    try:
        _start_worker(core)
        core.say("Детектор людей запущен")
    except Exception as e:
        core.say(f"Не удалось запустить детектор: {e}")

def _cmd_stop(core: Core, phrase: str):
    _stop_worker()
    core.say("Детектор людей остановлен")

def _cmd_how_many(core: Core, phrase: str):
    with _state_lock:
        cnt = _last_count
    if cnt == 0:
        core.say("Людей не обнаружено")
    elif cnt == 1:
        core.say("Обнаружен один человек")
    else:
        core.say(f"Обнаружено людей: {cnt}")

def _cmd_alert_on(core: Core, phrase: str):
    global _alert_enabled
    with _state_lock:
        _alert_enabled = True
    core.say("Оповещение включено")

def _cmd_alert_off(core: Core, phrase: str):
    global _alert_enabled
    with _state_lock:
        _alert_enabled = False
    core.say("Оповещение выключено")

def _start_worker(core: Core):
    global _worker, _stop_evt
    if _worker and _worker.is_alive():
        return

    opts = core.extension_options(modname) or {}
    prototxt = os.path.join(opts.get("model_dir", ""), opts.get("prototxt", "deploy.prototxt"))
    weights = os.path.join(opts.get("model_dir", ""), opts.get("weights", "mobilenet_iter_73000.caffemodel"))

    _ensure_models(core, prototxt, weights, opts)

    net = cv2.dnn.readNetFromCaffe(prototxt, weights)
    if bool(opts.get("use_cuda", False)):
        try:
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        except Exception:
            pass

    source = opts.get("camera_source", 0)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError("Не удалось открыть источник камеры")

    poll_ms = int(opts.get("poll_ms", 400))
    conf_thr = float(opts.get("confidence", 0.5))
    in_w = int(opts.get("resize_width", 640))
    in_h = int(opts.get("resize_height", 480))

    _stop_evt = threading.Event()

    def _loop():
        global _last_count, _last_alert_ts
        try:
            while not _stop_evt.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(poll_ms / 1000.0)
                    continue

                if in_w > 0 and in_h > 0:
                    frame = cv2.resize(frame, (in_w, in_h))

                blob = cv2.dnn.blobFromImage(frame, scalefactor=0.007843, size=(300, 300), mean=(127.5, 127.5, 127.5), swapRB=False, crop=False)
                net.setInput(blob)

                # [1, 1, N, 7] - (image_id, label, confidence, x1,y1,x2,y2)
                detections = net.forward()

                count = 0
                for i in range(detections.shape[2]):
                    conf = float(detections[0, 0, i, 2])
                    if conf < conf_thr:
                        continue
                    cls_id = int(detections[0, 0, i, 1])
                    # MobileNet-SSD класс person id=15
                    if cls_id == 15:
                        count += 1

                alert_now = False
                ts = time.time()
                with _state_lock:
                    prev = _last_count
                    _last_count = count
                    if _alert_enabled and count > 0 and (ts - _last_alert_ts) >= float(opts.get("alert_min_interval", 10)):
                        alert_now = True
                        _last_alert_ts = ts

                if alert_now:
                    try:
                        msg = "Обнаружен человек" if count == 1 else f"Обнаружено людей: {count}"
                        core.say(msg)
                    except Exception:
                        pass

                time.sleep(poll_ms / 1000.0)
        finally:
            cap.release()

    _worker = threading.Thread(target=_loop, name="person_watch_worker", daemon=True)
    _worker.start()

def _stop_worker():
    global _worker, _stop_evt
    if _stop_evt:
        _stop_evt.set()

    if _worker:
        _worker.join(timeout=2.0)

    _worker = None
    _stop_evt = None

def _ensure_models(core: Core, prototxt: str, weights: str, opts: dict):
    os.makedirs(os.path.dirname(prototxt), exist_ok=True)

    need_prototxt = not os.path.isfile(prototxt)
    need_weights = not os.path.isfile(weights)

    if not need_prototxt and not need_weights:
        return

    missing = []
    if need_prototxt:
        missing.append(os.path.basename(prototxt))

    if need_weights:
        missing.append(os.path.basename(weights))

    raise FileNotFoundError("Отсутствуют файлы модели: " + ", ".join(missing))
