import os
import json
import traceback
from typing import Any, Dict
from app.core.core import Core

from fastapi import WebSocket
from app.utils.fastapi_utils_tasks import repeat_every

try:
    from vosk import Model, KaldiRecognizer
    _vosk_available = True
except Exception:
    _vosk_available = False

"""
    Плагин регистрирует все HTTP и WebSocket, если core.fastApiApp присутствует

    Опции
        enable_ws_asr - включить WS-распознавание через Vosk
        model_path - путь к модели Vosk
"""

modname = os.path.basename(__package__)[12:]

def start(core: Core):
    manifest = {
        "name": "API",

        "options": {
            "enable_ws_asr": True,
            "model_path": "./app/models/vosk"
        }
    }

    app = getattr(core, "fastApiApp", None)
    if app is None:
        #core.print_red("[api] FastAPI app не найден (core.fastApiApp is None)- плагин в пассивном режиме")
        return manifest

    _register_http_routes(core, app)

    _register_ws_text_routes(core, app)

    cfg = _get_opts(core, modname, manifest["options"])
    enable_ws_asr: bool = bool(cfg["enable_ws_asr"])

    if enable_ws_asr and _vosk_available:
        try:
            model_path: str = cfg["model_path"]
            model = Model(model_path)
            _register_ws_asr_routes(core, app, model)
        except Exception:
            traceback.print_exc()
            core.print_red("[api] Не удалось инициализировать модель Vosk. WS ASR будет выключен.")
    else:
        core.print_red("[api] WS ASR выключен (enable_ws_asr=False или нет Vosk)")

    # Периодический апдейт таймеров
    @app.on_event("startup")
    @repeat_every(seconds=2)
    async def _update_timers_job():
        core.update_timers()

    return manifest

def _register_http_routes(core: Core, app):
    @app.get("/tts-wav")
    async def tts_wav(text: str):
        core.remoteTTS = "saywav"
        core.play_voice_assistant_speech(text)
        return core.remoteTTSResult

    @app.get("/send-txt-cmd")
    async def send_txt_cmd(cmd: str, format: str = "none"):
        return _run_cmd(core, cmd, format)

    @app.get("/send-raw-txt")
    async def send_raw_txt(txt: str, format: str = "none"):
        return _send_raw_txt(core, txt, format)

def _register_ws_text_routes(core: Core, app):
    @app.websocket("/ws-raw-text")
    async def ws_raw_text(websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                result = _send_raw_txt(
                    core,
                    payload.get("txt", ""),
                    payload.get("format", "none"),
                )
                await websocket.send_text(str(result))
            except Exception as e:
                core.print_red(f"[api] Invalid JSON: {e}")

    @app.websocket("/ws-raw-text-cmd")
    async def ws_raw_text_cmd(websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                result = _run_cmd(
                    core,
                    payload.get("txt", ""),
                    payload.get("format", "none"),
                )
                await websocket.send_text(str(result))
            except Exception as e:
                core.print_red(f"[api] Invalid JSON: {e}")

"""
    Регистрирует три однотипных ASR WS-эндпоинта через фабрику
"""
def _register_ws_asr_routes(core, app, model: "Model"):

    def make_ws(path: str, samplerate: int, return_format: str):
        @app.websocket(path)
        async def _ws(websocket: WebSocket):
            await websocket.accept()
            rec = KaldiRecognizer(model, samplerate)
            while True:
                data = await websocket.receive_bytes()
                await websocket.send_text(_process_chunk(core, rec, data, return_format))

    # 48000 + возвращаем и текст и wav
    make_ws("/ws-mic", 48000, "saytxt,saywav")

def _get_opts(core, plugin_name: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    saved = core.plugin_options(plugin_name) or {}
    # saved перекрывает defaults
    return {**defaults, **saved}

def _run_cmd(core, cmd: str, return_format: str):
    core.remoteTTS = return_format
    core.remoteTTSResult = ""
    core.lastSay = ""
    core.execute_next(cmd, core.context)
    return core.remoteTTSResult

def _send_raw_txt(core, txt: str, return_format: str = "none"):
    core.remoteTTS = return_format
    core.remoteTTSResult = ""
    core.lastSay = ""
    is_found = core.run_input_str(txt)
    return core.remoteTTSResult if is_found else "NO_VA_NAME"

"""
    Поведение:
        на финальной фразе шлём в ядро текст -> получаем ответ (saytxt/saywav)
        иначе отдаём partial/empty
"""
def _process_chunk(core, rec, message: bytes | str, return_format: str):
    if message == b'{"eof" : 1}' or message == '{"eof" : 1}':
        return rec.FinalResult()

    if rec.AcceptWaveform(message):
        resj = json.loads(rec.Result())
        text = resj.get("text", "")
        if text:
            result = _send_raw_txt(core, text, return_format)
            if result != "NO_VA_NAME" and isinstance(result, dict) and "wav_base64" in result:
                # bytes -> str
                result["wav_base64"] = result["wav_base64"].decode("utf-8")
                return json.dumps(result)
        return "{}"

    return rec.PartialResult()
