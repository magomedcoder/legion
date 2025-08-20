import os
import json
import math
import shlex
import subprocess
import soundfile as sf
import numpy as np

from typing import Any, Dict, Optional, List, Tuple
from app.core.core import Core

try:
    import gigaam
except Exception:
    pass

"""
    Файл с аудио в текст (GigaAM)

    pip install git+https://github.com/salute-developers/GigaAM.git

    Опции:
        model_name (str)       - имя модели (ctc, v2_ctc, rnnt, v2_rnnt, v1_rnnt, v1_ctc)
        ffmpeg_cmd (str)       - ffmpeg
        target_sr (int)        - частота дискретизации для нормализации (16000)
        safe_sec (float)       - длительность чанка (19.5 сек)
        say_result (bool)      - озвучивать ли результат
        save_json_path (str)   - путь для сохранения JSON
        save_srt_path (str)    - путь для сохранения субтитров .srt

    Команды:
        gigaam распознай файл runtime/test.mp3
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "Файл с аудио в текст (GigaAM)",

        "options": {
            "model_name": "v2_rnnt",
            "ffmpeg_cmd": "ffmpeg",
            "target_sr": 16000,
            "safe_sec": 19.5,
            "say_result": False,
            "save_json_path": "out/giga-file-stt.json",
            "save_srt_path": "out/giga-file-stt.srt",
        },

        "commands": {
            "gigaam распознай файл": _entry_stt,
        }
    }

_model = None

def start(core: Core, manifest: Dict[str, Any]) -> None:
    pass

def _entry_stt(core: Core, phrase: str):
    opts = core.extension_options(__package__) or {}
    ffmpeg_cmd: str = opts.get("ffmpeg_cmd")
    model_name: str = opts.get("model_name")
    target_sr: int = int(opts.get("target_sr"))
    safe_sec: float = float(opts.get("safe_sec"))
    say_result: bool = bool(opts.get("say_result"))
    save_json_path: str = opts.get("save_json_path")
    save_srt_path: str = opts.get("save_srt_path")

    path = _parse_path_from_phrase(phrase)
    if not path or not os.path.exists(path):
        core.say("Укажи существующий путь к аудиофайлу")
        return

    try:
        model = _ensure_model(model_name)
    except Exception as e:
        core.say(f"Ошибка загрузки модели GigaAM: {e}")
        return

    try:
        wav16 = _to_wav16k_mono(ffmpeg_cmd, path, target_sr)
        chunks = _slice_wav_safe(wav16, target_sr, safe_sec)
    except Exception as e:
        core.say(f"Ошибка подготовки аудио: {e}")
        return

    parts: List[Dict[str, Any]] = []
    full_text: List[str] = []

    try:
        for chunk_path, start, dur in chunks:
            try:
                text = model.transcribe(chunk_path)
            except Exception as e:
                core.say(f"Ошибка транскрипции: {e}")
                continue

            parts.append({"text": text, "start": start, "end": start + dur})
            if text:
                full_text.append(text)

        text_final = " ".join(full_text).strip()
    except Exception as e:
        core.say(f"Ошибка обработки чанков: {e}")
        return

    try:
        if save_json_path:
            _safe_mkdir(os.path.dirname(save_json_path))
            with open(save_json_path, "w", encoding="utf-8") as f:
                json.dump({"text": text_final, "phrases": parts}, f, ensure_ascii=False, indent=2)

        if save_srt_path and parts:
            _safe_mkdir(os.path.dirname(save_srt_path))
            srt = _make_srt(parts)
            with open(save_srt_path, "w", encoding="utf-8") as f:
                f.write(srt)
    except Exception:
        pass

    if not text_final:
        core.say("Распознать не удалось или файл пуст")
        return

    if say_result:
        core.say(text_final)
    else:
        prev = core.remote_tts
        try:
            if prev == "none":
                core.remote_tts = "saytxt"
            elif "saytxt" not in prev:
                core.remote_tts = prev + ",saytxt"
            core.play_voice_assistant_speech(text_final)
        finally:
            core.remote_tts = prev

def _ensure_model(model_name: str):
    global _model
    if _model is not None:
        return _model
    _model = gigaam.load_model(model_name=model_name)
    return _model

def _to_wav16k_mono(ffmpeg_cmd: str, src: str, target_sr: int) -> str:
    out_wav = "runtime/stt-file-gigaam/audio_16k_mono.wav"
    subprocess.run([ffmpeg_cmd, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-ar", str(target_sr), "-ac", "1", out_wav], check=True)
    return out_wav

def _slice_wav_safe(in_wav: str, sr: int, max_sec: float) -> List[Tuple[str, float, float]]:
    y, sr2 = sf.read(in_wav, always_2d=False)
    if y.ndim > 1:
        y = y[:, 0]

    max_samps = int(max_sec * sr) - 32
    total = len(y)
    n = math.ceil(total / max_samps)

    out = []
    os.makedirs("runtime/stt-file-gigaam/chunks", exist_ok=True)
    for i in range(n):
        s = i * max_samps
        e = min(s + max_samps, total)
        part = y[s:e].astype(np.float32, copy=False)

        out_path = f"runtime/chunks/stt-file-gigaam/chunk_{i:04d}.wav"
        sf.write(out_path, part, sr)

        start_sec = s / sr
        dur_sec = (e - s) / sr
        out.append((out_path, start_sec, dur_sec))

    return out

def _parse_path_from_phrase(text: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    tokens = shlex.split(text)
    if not tokens:
        return None
    if tokens[0].lower() in {"на", "в"} and len(tokens) > 1:
        tokens = tokens[1:]
    return tokens[-1]

def _safe_mkdir(dirpath: str):
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)

def _srt_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000.0))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _make_srt(parts: List[Dict[str, Any]]) -> str:
    lines = []
    for i, p in enumerate(parts, start=1):
        txt = (p.get("text") or "").strip()
        if not txt:
            continue
        start = float(p.get("start") or 0.0)
        end = float(p.get("end") or start)
        lines.append(f"{i}\n{_srt_time(start)} --> {_srt_time(end)}\n{txt}\n")
    return "\n".join(lines)
