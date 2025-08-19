import os
import json
import shlex
import subprocess
from typing import Any, Dict, Optional

from app.core.core import Core

try:
    from vosk import Model, KaldiRecognizer
    _vosk_available = True
except Exception:
    _vosk_available = False

"""
    Файл с аудио в текст

    Опции:
        model_path: str     - путь к модели Vosk
        sample_rate: int    - частота дискретизации для распознавания
        ffmpeg_cmd: str     - команда запуска ffmpeg
        say_result: bool    - озвучивать ли распознанный текст
        return_words: bool  - включать ли слова/таймкоды в результат
        max_seconds: int    - максимальная длительность входного файла в секундах
        save_json_path: str - путь для сохранения raw JSON результата
        save_srt_path: str  - путь для сохранения субтитров .srt (используется при return_words=True)

    Команды:
        распознай файл runtime/test.mp3
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "Файл с аудио в текст",

        "options": {
            "model_path": "./app/models/vosk",
            "sample_rate": 16000,
            "ffmpeg_cmd": "ffmpeg",
            "say_result": False,
            "return_words": False,
            "max_seconds": 900,
            "save_json_path": "runtime/file-stt.json",
            "save_srt_path": "runtime/file-stt.srt",
        },

        "commands": {
            "распознай файл": _stt_entry,
        }
    }

def start(core: Core, manifest: Dict[str, Any]) -> None:
    pass

def _parse_path_from_phrase(phrase: str) -> Optional[str]:
    text = (phrase or "").strip()
    if not text:
        return None

    tokens = shlex.split(text) if text else []
    if tokens:
        if tokens[0].lower() in {"на"} and len(tokens) > 1:
            tokens = tokens[1:]
        candidate = tokens[-1]
        return candidate

    return text.split()[-1] if text else None

"""
    Возвращает subprocess.Popen, который гонит в stdout сырые PCM (s16le, mono, sample_rate)
    Бросит FileNotFoundError, если ffmpeg не найден
"""
def _ffmpeg_decode_to_pcm(ffmpeg_cmd: str, path: str, sample_rate: int):
    cmd = [ffmpeg_cmd, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "pipe:1"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE)

"""
    Возвращает длительность файла в секундах через ffprobe
    Если ffprobe недоступен - вернёт None
"""
def _sec_from_ffprobe(ffmpeg_cmd: str, path: str) -> Optional[float]:
    ffprobe = ffmpeg_cmd.replace("ffmpeg", "ffprobe")
    try:
        out = subprocess.check_output(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
        return float(out) if out else None
    except Exception:
        return None

"""
    Простая генерация SRT из списка слов {word,start,end}
    Склеиваем по ~5–7 слов в субтитр
"""
def _make_srt(words: list[dict]) -> str:
    lines = []
    idx = 1
    buf = []
    for w in words:
        buf.append(w)
        if len(buf) >= 6:
            start = buf[0]["start"]
            end = buf[-1]["end"]
            text = " ".join(x["word"] for x in buf)
            lines.append(_srt_block(idx, start, end, text))
            idx += 1
            buf = []

    if buf:
        start = buf[0]["start"]
        end = buf[-1]["end"]
        text = " ".join(x["word"] for x in buf)
        lines.append(_srt_block(idx, start, end, text))

    return "\n".join(lines)

def _srt_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _srt_block(idx: int, start: float, end: float, text: str) -> str:
    return f"{idx}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n"

"""
    Точка входа для команд распознай файл ...”
"""
def _stt_entry(core: Core, phrase: str):
    if not _vosk_available:
        core.say("Библиотека Vosk недоступна")
        return

    opts = core.extension_options(__package__)
    model_path = opts["model_path"]
    sample_rate = int(opts["sample_rate"])
    ffmpeg_cmd = opts["ffmpeg_cmd"]
    say_result = bool(opts["say_result"])
    return_words = bool(opts["return_words"])
    max_seconds = int(opts["max_seconds"])
    save_json_path = (opts.get("save_json_path") or "").strip()
    save_srt_path = (opts.get("save_srt_path") or "").strip()

    path = _parse_path_from_phrase(phrase)
    if not path or not os.path.exists(path):
        core.say("Укажите существующий путь к аудиофайлу")
        return

    if not os.path.isdir(model_path):
        core.say(f"Модель Vosk не найдена по пути: {model_path}")
        return

    dur = _sec_from_ffprobe(ffmpeg_cmd, path)
    if dur is not None and max_seconds > 0 and dur > max_seconds:
        core.say(f"Файл слишком длинный ({int(dur)} сек). Максимум: {max_seconds} сек")
        return

    try:
        model = Model(model_path)
    except Exception:
        core.say("Не удалось загрузить модель Vosk")
        return

    try:
        proc = _ffmpeg_decode_to_pcm(ffmpeg_cmd, path, sample_rate)
    except FileNotFoundError:
        core.say("Не найден ffmpeg")
        return
    except Exception:
        core.say("Не удалось декодировать аудио через ffmpeg")
        return

    rec = KaldiRecognizer(model, sample_rate)
    if return_words:
        try:
            rec.SetWords(True)
        except Exception:
            pass

    # Читаем поток PCM и кормим распознавателю
    full_text = []
    words_all = []
    try:
        while True:
            chunk = proc.stdout.read(4000)
            if not chunk:
                break

            if rec.AcceptWaveform(chunk):
                part = json.loads(rec.Result())
                if "text" in part and part["text"]:
                    full_text.append(part["text"])

                if return_words and "result" in part:
                    words_all.extend(part["result"])

        final = json.loads(rec.FinalResult())
        if "text" in final and final["text"]:
            full_text.append(final["text"])

        if return_words and "result" in final:
            words_all.extend(final["result"])
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass

        try:
            proc.kill()
        except Exception:
            pass

    text = " ".join([t for t in full_text if t]).strip()

    try:
        if save_json_path:
            with open(save_json_path, "w", encoding="utf-8") as f:
                json.dump({"text": text, "words": words_all}, f, ensure_ascii=False, indent=2)

        if save_srt_path and words_all:
            srt = _make_srt(words_all)
            with open(save_srt_path, "w", encoding="utf-8") as f:
                f.write(srt)
    except Exception:
        pass

    if not text:
        core.say("Распознать не удалось или файл пуст")
        return

    if say_result:
        core.say(text)
    else:
        prev = core.remote_tts
        try:
            if prev == "none":
                core.remote_tts = "saytxt"
            elif "saytxt" not in prev:
                core.remote_tts = prev + ",saytxt"
            core.play_voice_assistant_speech(text)
        finally:
            core.remote_tts = prev
