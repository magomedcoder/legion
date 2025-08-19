import json
from typing import Union, Dict, Any

from app.core.core import Core
from .models import CommonResponse, ReturnFormat

def map_format(fmt: ReturnFormat) -> str:
    if fmt == ReturnFormat.both:
        return "saytxt,saywav"

    return fmt.value

def run_cmd(core: Core, cmd: str, format: str):
    core.remote_tts = format
    core.remote_tts_result = ""
    core.last_say = ""
    core.execute_next(cmd, core.context)
    return core.remote_tts_result

def send_raw_txt(core: Core, txt: str, format: str = "none"):
    core.remote_tts = format
    core.remote_tts_result = ""
    core.last_say = ""
    is_found = core.run_input_str(txt)
    return core.remote_tts_result if is_found else "NO_VA_NAME"

"""
    Приводит текущие форматы (none | {text} | {wav_base64} | оба) к CommonResponse
"""
def normalize_speech_response(result: Union[str, dict]) -> CommonResponse:
    if result == "" or result is None:
        return CommonResponse()

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            return CommonResponse(text=result)
    if isinstance(result, dict):
        text = result.get("txt") or result.get("text")
        wav_b64 = result.get("wav_base64")

        if isinstance(wav_b64, (bytes, bytearray)):
            wav_b64 = wav_b64.decode("utf-8")

        return CommonResponse(text=text, wav_base64=wav_b64)
    return CommonResponse()

"""
    Обрабатывает пришедший аудиочанк
    Возвращает
        {
            "heard": "<partial|final>",
            "text": "reply|null>",
            "wav_base64": "<base6|null>"
        }
"""
def process_chunk(core: Core, rec, message: bytes | str, format: str) -> Dict[str, Any]:
    if message == b'{"eof" : 1}' or message == '{"eof" : 1}':
        try:
            final = json.loads(rec.FinalResult() or "{}")
        except Exception:
            final = {}
        heard = final.get("text") or None
        return {"heard": heard, "text": None, "wav_base64": None}

    if rec.AcceptWaveform(message):
        try:
            resj = json.loads(rec.Result() or "{}")
        except Exception:
            resj = {}
        text = resj.get("text", "") or ""

        if text:
            result = send_raw_txt(core, text, format)

            if result != "NO_VA_NAME":
                norm = normalize_speech_response(result)
                return {
                    "heard": text,
                    "text": norm.text,
                    "wav_base64": norm.wav_base64,
                }
            else:
                return {
                    "heard": text,
                    "text": None,
                    "wav_base64": None,
                }

        return {
            "heard": None,
            "text": None,
            "wav_base64": None,
        }

    try:
        partial = json.loads(rec.PartialResult() or "{}")
    except Exception:
        partial = {}
    heard_partial = partial.get("partial") or None
    return {"heard": heard_partial, "text": None, "wav_base64": None}
