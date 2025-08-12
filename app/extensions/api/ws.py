import json
from fastapi import FastAPI, WebSocket
from vosk import Model, KaldiRecognizer
from app.core.core import Core
from .utils import send_raw_txt, run_cmd, normalize_speech_response, process_chunk

def attach_ws(core: Core, app: FastAPI, model: Model) -> None:
    @app.websocket("/ws/asr/stream")
    async def ws_asr_stream(websocket: WebSocket):
        # 48kHz + возвращаем и текст, и wav
        await websocket.accept()
        rec = KaldiRecognizer(model, 48000)
        while True:
            data = await websocket.receive_bytes()
            await websocket.send_text(process_chunk(core, rec, data, "saytxt,saywav"))

    @app.websocket("/ws/commands")
    async def ws_commands(websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                result = run_cmd(core, payload.get("text", ""), payload.get("format", "none"))
                await websocket.send_text(json.dumps(normalize_speech_response(result).model_dump()))
            except Exception as e:
                core.print_red(f"[api] Некорректный JSON: {e}")

    @app.websocket("/ws/utterances")
    async def ws_utterances(websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                result = send_raw_txt(core, payload.get("text", ""), payload.get("format", "none"))
                await websocket.send_text(json.dumps(normalize_speech_response(result).model_dump()))
            except Exception as e:
                core.print_red(f"[api] Некорректный JSON: {e}")