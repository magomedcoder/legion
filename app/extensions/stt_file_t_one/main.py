import os
import json
import shlex
import subprocess
import struct
import shutil
import traceback

from typing import Any, Dict, Optional, List
from app.core.core import Core

try:
    from tone import StreamingCTCPipeline, read_audio
except Exception:
    pass

"""
    Файл с аудио в текст (T-one)

    pip install git+https://github.com/voicekit-team/T-one.git
    pip install miniaudio

    Опции:
        ffmpeg_cmd (str)        - ffmpeg
        sample_rate (int)       - частота дискретизации PCM при декоде через ffmpeg (обычно 16000)
        say_result (bool)       - озвучивать ли распознанный текст
        return_phrases (bool)   - возвращать ли фразы с таймкодами (включает стриминговый прогон)
        max_seconds (int)       - максимально допустимая длительность файла, сек (0 - без проверки)
        save_json_path (str)    - путь для сохранения raw JSON результата
        save_srt_path (str)     - путь для сохранения субтитров .srt

    Команды:
        t-one распознай файл runtime/test.mp3
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "Файл с аудио в текст (T-one)",

        "options": {
            "sample_rate": 16000,
            "say_result": False,
            "return_phrases": False,
            "max_seconds": 0,
            "save_json_path": "out/tone-file-stt.json",
            "save_srt_path": "out/tone-file-stt.srt",
        },

        "commands": {
            "t-one распознай файл": _entry_stt,
        }
    }

_pipeline: Optional[StreamingCTCPipeline] = None

def start(core: Core, manifest: Dict[str, Any]) -> None:
    pass

def _entry_stt(core: Core, phrase: str):
    opts = core.extension_options(__package__)
    ffmpeg_cmd: str = opts.get("ffmpeg_cmd")
    sr: int = int(opts.get("sample_rate"))
    say_result: bool = bool(opts.get("say_result"))
    return_phrases: bool = bool(opts.get("return_phrases"))
    max_seconds: int = int(opts.get("max_seconds"))
    save_json_path: str = opts.get("save_json_path")
    save_srt_path: str = opts.get("save_srt_path")

    path = _parse_path_from_phrase(phrase)
    if not path or not os.path.exists(path):
        core.say("Укажи существующий путь к аудиофайлу")
        return

    dur = _sec_from_ffprobe(ffmpeg_cmd, path)
    if dur is not None and max_seconds > 0 and dur > max_seconds:
        core.say(f"Файл слишком длинный ({int(dur)} сек). Максимум: {max_seconds} сек")
        return

    if return_phrases:
        if not shutil.which(ffmpeg_cmd):
            core.say(f"Не найден ffmpeg ('{ffmpeg_cmd}')")
            return
        if not shutil.which(ffmpeg_cmd.replace("ffmpeg", "ffprobe")):
            core.say(f"Не найден ffprobe")
            return

    pipeline, err = _ensure_pipeline()
    if pipeline is None:
        core.say(f"Не удалось инициализировать T-one пайплайн: {err or 'см. логи'}")
        return

    text: str = ""
    phrases: List[Dict[str, Any]] = []

    try:
        if not return_phrases:
            audio = read_audio(path)
            res = pipeline.forward_offline(audio)
            text, phrases = _normalize_offline_result(res)
        else:
            for new_phrases in _stream_pcm_through_tone(ffmpeg_cmd, path, sr, pipeline):
                if not new_phrases:
                    continue
                for p in new_phrases:
                    norm = {
                        "text": (p.get("text") or "").strip(),
                        "start": _first_present(p, ["start", "start_s", "begin", "t0", "start_time"], default=0.0),
                        "end": _first_present(p, ["end", "end_s", "finish", "t1", "end_time"], default=0.0),
                    }
                    if norm["text"]:
                        phrases.append(norm)
            text = " ".join(p["text"] for p in phrases if p["text"]).strip()
    except Exception as e:
        core.say(f"Ошибка распознавания через T-one: {e}")
        return

    try:
        if save_json_path:
            _safe_mkdir(os.path.dirname(save_json_path))
            with open(save_json_path, "w", encoding="utf-8") as f:
                json.dump({"text": text, "phrases": phrases}, f, ensure_ascii=False, indent=2)

        if save_srt_path and phrases:
            _safe_mkdir(os.path.dirname(save_srt_path))
            srt = _make_srt_from_phrases(phrases)
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

def _ensure_pipeline() -> tuple[Optional[StreamingCTCPipeline], Optional[str]]:
    global _pipeline
    if _pipeline is not None:
        return _pipeline, None
    try:
        _pipeline = StreamingCTCPipeline.from_hugging_face()
        return _pipeline, None
    except Exception as e:
        err = f"{e}\n{traceback.format_exc(limit=5)}"
        print("[T-one]\n", err)
        return None, str(e)

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

def _sec_from_ffprobe(ffmpeg_cmd: str, path: str) -> Optional[float]:
    ffprobe = (ffmpeg_cmd or "ffmpeg").replace("ffmpeg", "ffprobe")
    try:
        out = subprocess.check_output(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stderr=subprocess.STDOUT, text=True,
        ).strip()
        return float(out) if out else None
    except Exception:
        return None

def _stream_pcm_through_tone(ffmpeg_cmd: str, path: str, sample_rate: int, pipeline: StreamingCTCPipeline):
    cmd = [ffmpeg_cmd or "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    state = None

    try:
        bytes_per_chunk = int(sample_rate * 0.3) * 2
        while True:
            buf = proc.stdout.read(bytes_per_chunk)
            if not buf:
                break
            count = len(buf) // 2
            if count <= 0:
                continue

            samples = struct.unpack("<" + "h" * count, buf)
            audio_chunk = [x / 32768.0 for x in samples]

            new_phrases, state = pipeline.forward(audio_chunk, state)
            if new_phrases:
                yield new_phrases

        new_phrases, _ = pipeline.finalize(state)
        if new_phrases:
            yield new_phrases
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass

def _first_present(d: Dict[str, Any], keys: List[str], default: float) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except Exception:
                pass
    return float(default)

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

def _make_srt_from_phrases(phrases: List[Dict[str, Any]]) -> str:
    lines = []
    idx = 1
    for p in phrases:
        txt = (p.get("text") or "").strip()
        if not txt:
            continue
        start = float(p.get("start") or 0.0)
        end = float(p.get("end") or start)
        lines.append(f"{idx}\n{_srt_time(start)} --> {_srt_time(end)}\n{txt}\n")
        idx += 1
    return "\n".join(lines)

def _normalize_offline_result(res) -> tuple[str, List[Dict[str, Any]]]:
    if isinstance(res, str):
        return res.strip(), []

    if isinstance(res, dict):
        text = (res.get("text") or "").strip()
        phrases_raw = res.get("phrases") or res.get("segments") or []
        phrases = _normalize_phrases_list(phrases_raw)
        if not text and phrases:
            text = " ".join(p["text"] for p in phrases if p["text"]).strip()
        return text, phrases

    if isinstance(res, list):
        if not res:
            return "", []
        if isinstance(res[0], dict):
            phrases = _normalize_phrases_list(res)
            text = " ".join(p["text"] for p in phrases if p["text"]).strip()
            return text, phrases

        text = " ".join(str(x).strip() for x in res if x is not None).strip()
        return text, []

    return (str(res).strip() if res is not None else ""), []


def _normalize_phrases_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in items or []:
        if not isinstance(p, dict):
            out.append({"text": str(p).strip(), "start": 0.0, "end": 0.0})
            continue
        out.append({
            "text": (p.get("text") or "").strip(),
            "start": _first_present(p, ["start", "start_s", "begin", "t0", "start_time"], 0.0),
            "end": _first_present(p, ["end", "end_s", "finish", "t1", "end_time"], 0.0),
        })
    return out
