import json
from fastapi import FastAPI, WebSocket
from vosk import Model, KaldiRecognizer
from app.core.core import Core
from .utils import send_raw_txt, run_cmd, normalize_speech_response, process_chunk

def attach_ws(core: Core, app: FastAPI, model: Model) -> None:

    """
        Принимает raw PCM16 LE mono 48kHz
            {
                "heard": "<partial|final>",
                "text": "reply|null>",
                "wav_base64": "<base6|null>"
            }
    """
    @app.websocket("/ws/asr/stream")
    async def ws_asr_stream(websocket: WebSocket):
        await websocket.accept()
        rec = KaldiRecognizer(model, 48000)

        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"] is not None:
                data = msg["bytes"]
                payload = process_chunk(core, rec, data, "saytxt,saywav")
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            elif "text" in msg and msg["text"] is not None:
                text = msg["text"]
                if text.strip() in ('{"eof" : 1}', '{"eof":1}', '{"eof": 1}'):
                    payload = process_chunk(core, rec, text, "saytxt,saywav")
                    await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                else:
                    await websocket.send_text(json.dumps(
                        {
                            "heard": None,
                            "text": None,
                            "wav_base64": None,
                        },
                        ensure_ascii=False
                    ))
            else:
                await websocket.send_text(json.dumps(
                    {
                        "heard": None,
                        "text": None,
                        "wav_base64": None,
                    },
                    ensure_ascii=False
                ))

    @app.websocket("/ws/commands")
    async def ws_commands(websocket: WebSocket):
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                result = run_cmd(core, payload.get("text", ""), payload.get("format", "none"))
                await websocket.send_text(json.dumps(
                    normalize_speech_response(result).model_dump(),
                    ensure_ascii=False
                ))
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
                await websocket.send_text(json.dumps(
                    normalize_speech_response(result).model_dump(),
                    ensure_ascii=False
                ))
            except Exception as e:
                core.print_red(f"[api] Некорректный JSON: {e}")