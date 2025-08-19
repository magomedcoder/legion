import os
import json
import shlex
import tempfile
import subprocess
import librosa
import soundfile as sf
import numpy as np
import torch
from typing import Any, Dict, Optional, List, Tuple
from vosk import Model, KaldiRecognizer
from app.core.core import Core

try:
    from speechbrain.inference import EncoderClassifier
    from sklearn.cluster import AgglomerativeClustering
except Exception:
    pass

"""
    Расширение: Голос -> Текст + Диаризация (определение спикеров)

    # pip install scikit-learn speechbrain librosa torch torchaudio --extra-index-url https://download.pytorch.org/whl/cu121

    Команды:
        голос в текст runtime/test.mp3
        распознай голоса runtime/test.mp3

    Опции:
        vosk_model_path (str) - путь к директории модели Vosk
        sample_rate (int) - целевая частота дискретизации WAV для распознавания (Гц)
        ffmpeg_cmd (str) имя или полный путь к исполняемому файлу ffmpeg
        say_result (bool) - озвучивать ли распознанный текст
        return_words (bool) - возвращать ли слова с таймкодами от Vosk (нужно для точного SRT)
        max_seconds (int) ограничение длительности входного файла в секундах (0 — без ограничения)
        enable_diarization (bool) включить диаризацию при наличии зависимостей (speechbrain, scikit-learn)
        num_speakers (int) - 0 — автооценка- >0 — фиксированное число кластеров
        window_sec (float) - длина окна (сек) для спикер-эмбеддингов
        hop_sec (float) - шаг окна (сек)
        min_silence_merge (float) - склейка соседних сегментов одного спикера, если пауза между ними не превышает указанное значение (сек)
        save_json_path (str) - путь для сохранения полного результата в JSON
        save_srt_path (str) - путь для сохранения субтитров SRT
        device (str) - cpu | cuda
        cpu_num_threads (int) - >0 ограничить torch.set_num_threads
        batch_seconds (float) - батчинг сегментов при диаризации (0 = выкл)

    Структура выходных данных:
        {
            "text": str, - распознанный текст
            "words": [ - слова поштучно с таймкодами
                {
                    "word": str, - слово
                    "start": float, - начало слова в секундах
                    "end": float - конец слова в секундах
                }
            ],
            "speakers": [ - куски аудио кто говорит
                {
                    "start": float, -  начало сегмента (сек)
                    "end": float, - конец сегмента (сек)
                    "spk": int - индекс спикера: 0,1,2
                }
            ],
            "blocks": [ - фразы собранные из words и размеченные по спикерам
                {
                    "start": float, - начало фразы (первое слово блока)
                    "end": float, - конец фразы (последнее слово блока)
                    "spk": int, - индекс спикера для блока
                    "text": str - текст фразы (Пользователь spk+1 добавляется только в SRT)
                }
            ],
            "srt": str | null - SRT субтитры только у process_audio_file, в _run_pipeline в файл
        }
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "STT Диаризация (Vosk + SpeechBrain)",

        "options": {
            "vosk_model_path": "./app/models/vosk",
            "sample_rate": 16000,
            "ffmpeg_cmd": "ffmpeg",
            "say_result": False,
            "return_words": True,
            "max_seconds": 5400,
            "enable_diarization": True,
            "num_speakers": 0,
            "window_sec": 1.5,
            "hop_sec": 0.75,
            "min_silence_merge": 0.4,
            "save_json_path": "./out/stt-speaker-vosk-speechbrain.json",
            "save_srt_path": "./out/stt-speaker-vosk-speechbrain.srt",
            "device": "cpu",
            "cpu_num_threads": 0,
            "batch_seconds": 0.0,
        },

        "commands": {
            "голос в текст": _cmd_stt_only,
            "распознай голоса": _cmd_stt_speaker,
        }
    }

def start(core: Core, manifest: dict):
    pass

def _pick_device(opts: Dict[str, Any]) -> str:
    want = str(opts.get("device", "cpu")).lower()
    if want == "cuda":
        if torch.cuda.is_available():
            return "cuda"
        try:
            print("CUDA но недоступна переключаюсь на CPU")
        except Exception:
            pass
    return "cpu"

def _maybe_set_cpu_threads(opts: Dict[str, Any]):
    n = int(opts.get("cpu_num_threads", 0) or 0)
    if n > 0:
        try:
            torch.set_num_threads(n)
        except Exception:
            pass

def _parse_path(phrase: str) -> Optional[str]:
    text = (phrase or "").strip()
    if not text:
        return None
    # Раскрываем кавычки/пробелы
    try:
        tokens = shlex.split(text)
        if tokens:
            if tokens[0].lower() == "на" and len(tokens) > 1:
                tokens = tokens[1:]
            return tokens[-1]
    except Exception:
        pass
    return text.split()[-1] if text else None

def _ffmpeg_decode_wav(ffmpeg_cmd: str, path: str, sr: int) -> tuple[str, float]:
    fd, wav_path = tempfile.mkstemp(prefix="stt_", suffix=".wav")
    os.close(fd)

    try:
        if os.path.exists(wav_path):
            os.remove(wav_path)
    except Exception:
        pass

    # Длительность входного файла
    dur = _ffprobe_duration(ffmpeg_cmd, path)

    cmd = [ffmpeg_cmd, "-y", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-acodec", "pcm_s16le", wav_path]
    subprocess.run(cmd, check=True)

    if not os.path.exists(wav_path) or os.path.getsize(wav_path) <= 44:
        raise subprocess.CalledProcessError(returncode=1, cmd=" ".join(cmd), output="ffmpeg produced invalid WAV")

    # если ffprobe не дал длительность
    if dur is None:
        try:
            info = sf.info(wav_path)
            dur = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
        except Exception:
            dur = 0.0

    return wav_path, dur

def _agglo_fit_predict(X, n_clusters: int, metric: str = "cosine", linkage: str = "average"):
    try:
        model = AgglomerativeClustering(n_clusters=n_clusters, metric=metric, linkage=linkage)
        return model.fit_predict(X)
    except TypeError:
        model = AgglomerativeClustering(n_clusters=n_clusters, affinity=metric, linkage=linkage)
        return model.fit_predict(X)

def _ffprobe_duration(ffmpeg_cmd: str, path: str) -> Optional[float]:
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

def _read_wav_to_tensor(wav_path: str, target_sr: int) -> torch.Tensor:
    audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio[:, 0]
    if sr != target_sr:
        try:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
        except Exception:
            pass
    return torch.from_numpy(np.ascontiguousarray(audio))

def _run_vosk_stt(wav_path: str, sr: int, want_words: bool, model_dir: str) -> Tuple[str, List[dict]]:
    if not os.path.isdir(model_dir):
        raise RuntimeError(f"Модель Vosk не найдена по пути: {model_dir}")

    model = Model(model_dir)
    rec = KaldiRecognizer(model, sr)
    if want_words:
        try:
            rec.SetWords(True)
        except Exception:
            pass

    text_parts: List[str] = []
    words_all: List[dict] = []

    with open(wav_path, "rb") as f:
        # Пропускаем WAV-заголовок (44 байта) и читаем PCM
        _ = f.read(44)
        while True:
            chunk = f.read(4000)
            if not chunk:
                break

            if rec.AcceptWaveform(chunk):
                part = json.loads(rec.Result())
                if part.get("text"):
                    text_parts.append(part["text"])
                if want_words and part.get("result"):
                    words_all.extend(part["result"])

        final = json.loads(rec.FinalResult())
        if final.get("text"):
            text_parts.append(final["text"])
        if want_words and final.get("result"):
            words_all.extend(final["result"])

    full_text = " ".join([t for t in text_parts if t]).strip()
    words_norm = []
    for w in words_all:
        # vosk: {'conf': 0.9, 'end': 3.45, 'start': 3.15, 'word': 'привет'}
        if "word" in w and "start" in w and "end" in w:
            words_norm.append({"word": w["word"], "start": float(w["start"]), "end": float(w["end"])})

    return full_text, words_norm

def _speaker_diarization(wav_path: str, sr: int, window_sec: float, hop_sec: float, num_speakers: int = 0, min_merge_gap: float = 0.4, device: str = "cpu", batch_seconds: float = 0.0) -> List[dict]:
    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": device},
    )

    wav = _read_wav_to_tensor(wav_path, sr)
    total_len = wav.shape[0]
    win = int(sr * window_sec)
    hop = int(sr * hop_sec)
    # (s_i, e_i, t_s, t_e)
    frames: List[Tuple[int, int, float, float]] = []
    feats: List[np.ndarray] = []

    batch_win = max(1, int((batch_seconds / hop_sec))) if batch_seconds and batch_seconds > 0 else 1

    pos = 0
    with torch.no_grad():
        while pos + win <= total_len:
            batch_segments = []
            batch_times = []

            for _ in range(batch_win):
                if pos + win > total_len:
                    break

                seg = wav[pos: pos + win]
                batch_segments.append(seg)
                t_s = pos / sr
                t_e = (pos + win) / sr
                batch_times.append((pos, pos + win, t_s, t_e))
                pos += hop

            if not batch_segments:
                break

            batch_tensor = torch.stack(batch_segments, dim=0)

            emb = classifier.encode_batch(batch_tensor)

            if emb.ndim == 3 and emb.size(1) == 1:
                emb = emb.squeeze(1)
            elif emb.ndim != 2:
                emb = emb.reshape(emb.shape[0], -1)

            emb = emb.cpu().numpy()

            for (s_i, e_i, t_s, t_e), e in zip(batch_times, emb):
                frames.append((s_i, e_i, t_s, t_e))
                feats.append(e)

    if not feats:
        return []

    X = np.stack(feats)

    if num_speakers and num_speakers > 0:
        labels = _agglo_fit_predict(X, n_clusters=int(num_speakers), metric="cosine", linkage="average")
    else:
        best_labels = None
        best_score = None
        for k in range(2, min(6, X.shape[0] + 1)):
            cand_labels = _agglo_fit_predict(X, n_clusters=k, metric="cosine", linkage="average")
            score = _cluster_compactness(X, cand_labels)
            if best_score is None or score < best_score:
                best_score = score
                best_labels = cand_labels
        labels = best_labels if best_labels is not None else _agglo_fit_predict(X, n_clusters=2, metric="cosine", linkage="average")

    segs: List[dict] = []
    cur_spk = int(labels[0])
    cur_start = frames[0][2]
    cur_end = frames[0][3]

    for i in range(1, len(frames)):
        t_s, t_e = frames[i][2], frames[i][3]
        if int(labels[i]) == cur_spk and (t_s - cur_end) <= min_merge_gap:
            cur_end = t_e
        else:
            segs.append({"start": float(cur_start), "end": float(cur_end), "spk": int(cur_spk)})
            cur_spk = int(labels[i])
            cur_start = t_s
            cur_end = t_e

    segs.append({"start": float(cur_start), "end": float(cur_end), "spk": int(cur_spk)})
    return segs

def _cluster_compactness(X: np.ndarray, labels: np.ndarray) -> float:
    score = 0.0
    for lab in np.unique(labels):
        grp = X[labels == lab]
        c = grp.mean(axis=0, keepdims=True)
        d = 1.0 - (grp @ c.T) / (np.linalg.norm(grp, axis=1, keepdims=True) * np.linalg.norm(c))
        score += float(np.mean(d))
    return score

def _assign_words_to_speakers(words: List[dict], segs: List[dict]) -> List[dict]:
    if not words:
        return []
    if not segs:
        return [{"start": words[0]["start"], "end": words[-1]["end"], "spk": 0, "text": " ".join(w["word"] for w in words)}]

    def word_spk(w):
        w_s, w_e = w["start"], w["end"]
        best_spk, best_overlap = 0, 0.0
        for s in segs:
            ov = _overlap((w_s, w_e), (s["start"], s["end"]))
            if ov > best_overlap:
                best_overlap = ov
                best_spk = s["spk"]
        return best_spk

    labeled = []
    for w in words:
        spk = word_spk(w)
        labeled.append({"start": w["start"], "end": w["end"], "spk": spk, "word": w["word"]})

    blocks = []
    cur_spk = labeled[0]["spk"]
    cur_start = labeled[0]["start"]
    cur_end = labeled[0]["end"]
    cur_text = [labeled[0]["word"]]

    for w in labeled[1:]:
        if w["spk"] == cur_spk and (w["start"] - cur_end) <= 0.7:
            cur_end = w["end"]
            cur_text.append(w["word"])
        else:
            blocks.append({"start": cur_start, "end": cur_end, "spk": cur_spk, "text": " ".join(cur_text)})
            cur_spk = w["spk"]
            cur_start = w["start"]
            cur_end = w["end"]
            cur_text = [w["word"]]

    blocks.append({"start": cur_start, "end": cur_end, "spk": cur_spk, "text": " ".join(cur_text)})
    return blocks

def _overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    s = max(a[0], b[0]); e = min(a[1], b[1])
    return max(0.0, e - s)

def _srt_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _to_srt(blocks: List[dict]) -> str:
    lines = []
    for i, b in enumerate(blocks, 1):
        spk_name = f"Пользователь {b['spk'] + 1}"
        lines.append(f"{i}")
        lines.append(f"{_srt_time(b['start'])} --> {_srt_time(b['end'])}")
        lines.append(f"{spk_name}: {b['text']}")
        lines.append("")
    return "\n".join(lines)

def _cmd_stt_only(core: Core, phrase: str):
    _run_pipeline(core, phrase, with_diar=False)

def _cmd_stt_speaker(core: Core, phrase: str):
    _run_pipeline(core, phrase, with_diar=True)

def _run_pipeline(core: Core, phrase: str, with_diar: bool):
    opts = core.extension_options(__package__)

    _maybe_set_cpu_threads(opts)
    device = _pick_device(opts)

    path = _parse_path(phrase)
    if not path or not os.path.exists(path):
        core.say("Укажите существующий путь к аудиофайлу")
        return

    ffmpeg = opts["ffmpeg_cmd"]
    sr = int(opts["sample_rate"])
    want_words = bool(opts["return_words"])
    max_sec = int(opts["max_seconds"])

    try:
        wav_path, dur = _ffmpeg_decode_wav(ffmpeg, path, sr)
    except FileNotFoundError:
        core.say("Не найден ffmpeg")
        return
    except subprocess.CalledProcessError:
        core.say("Не удалось перекодировать файл через ffmpeg")
        return

    try:
        if max_sec > 0 and dur and dur > max_sec:
            core.say(f"Файл слишком длинный ({int(dur)} сек). Максимум: {max_sec} сек")
            return

        text, words = _run_vosk_stt(wav_path, sr, want_words, opts["vosk_model_path"])

        segments = []
        if with_diar and opts.get("enable_diarization", True):
            try:
                segments = _speaker_diarization(
                    wav_path=wav_path,
                    sr=sr,
                    window_sec=float(opts.get("window_sec", 1.5)),
                    hop_sec=float(opts.get("hop_sec", 0.75)),
                    num_speakers=int(opts.get("num_speakers", 0)),
                    min_merge_gap=float(opts.get("min_silence_merge", 0.4)),
                    device=device,
                    batch_seconds=float(opts.get("batch_seconds", 0.0)),
                )
            except Exception as e:
                segments = []
                try:
                    core.say(f"Диаризация недоступна: {e}")
                except Exception:
                    pass

        blocks = _assign_words_to_speakers(words, segments) if words else []
        save_json_path = (opts.get("save_json_path") or "").strip()
        save_srt_path = (opts.get("save_srt_path") or "").strip()

        result_obj = {"text": text, "words": words, "speakers": segments, "blocks": blocks}

        try:
            if save_json_path:
                os.makedirs(os.path.dirname(save_json_path), exist_ok=True)
                with open(save_json_path, "w", encoding="utf-8") as f:
                    json.dump(result_obj, f, ensure_ascii=False, indent=2)

            if save_srt_path and blocks:
                os.makedirs(os.path.dirname(save_srt_path), exist_ok=True)
                srt = _to_srt(blocks)
                with open(save_srt_path, "w", encoding="utf-8") as f:
                    f.write(srt)

        except Exception:
            pass

        if not text:
            core.say("Распознать не удалось или файл пуст")
            return

        if bool(opts.get("say_result", False)):
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

    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass

"""
    Обрабатывает аудиофайл и возвращает dict
        {"text": str, "words": [], "speakers": [], "blocks": [], "srt": str|None}
"""
def process_audio_file(core: Core, path: str, diarize: bool = True) -> dict:
    opts = core.extension_options(__package__)

    _maybe_set_cpu_threads(opts)
    device = _pick_device(opts)

    ffmpeg = opts["ffmpeg_cmd"]
    sr = int(opts["sample_rate"])
    want_words = bool(opts["return_words"])
    max_sec = int(opts["max_seconds"])

    wav_path, dur = _ffmpeg_decode_wav(ffmpeg, path, sr)
    try:
        if max_sec > 0 and dur and dur > max_sec:
            raise RuntimeError(f"Файл слишком длинный ({int(dur)} сек). Максимум: {max_sec} сек")

        text, words = _run_vosk_stt(wav_path, sr, want_words, opts["vosk_model_path"])

        segments = []
        if diarize and opts.get("enable_diarization", True):
            segments = _speaker_diarization(
                wav_path=wav_path,
                sr=sr,
                window_sec=float(opts.get("window_sec", 1.5)),
                hop_sec=float(opts.get("hop_sec", 0.75)),
                num_speakers=int(opts.get("num_speakers", 0)),
                min_merge_gap=float(opts.get("min_silence_merge", 0.4)),
                device=device,
                batch_seconds=float(opts.get("batch_seconds", 0.0)),
            )

        blocks = _assign_words_to_speakers(words, segments) if words else []
        srt = _to_srt(blocks) if blocks else None

        return {"text": text, "words": words, "speakers": segments, "blocks": blocks, "srt": srt}
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass
