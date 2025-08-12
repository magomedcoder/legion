import json
from typing import Union

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
        text = result.get("txt")
        wav_b64 = result.get("wav_base64")

        if isinstance(wav_b64, (bytes, bytearray)):
            wav_b64 = wav_b64.decode("utf-8")

        return CommonResponse(text=text, wav_base64=wav_b64)
    return CommonResponse()

"""
    При финальной фразе отправляем текст в ядро и получаем ответ (saytxt/saywav), иначе возвращаем partial или пустой результат
"""
def process_chunk(core: Core, rec, message: bytes | str, format: str):
    if message == b'{"eof" : 1}' or message == '{"eof" : 1}':
        return rec.FinalResult()

    if rec.AcceptWaveform(message):
        resj = json.loads(rec.Result())
        text = resj.get("text", "")
        if text:
            result = send_raw_txt(core, text, format)
            if result != "NO_VA_NAME" and isinstance(result, dict) and "wav_base64" in result:
                # bytes -> str
                result["wav_base64"] = (
                    result["wav_base64"].decode("utf-8")
                    if isinstance(result["wav_base64"], (bytes, bytearray))
                    else result["wav_base64"]
                )
                return json.dumps(result)
        return "{}"

    return rec.PartialResult()