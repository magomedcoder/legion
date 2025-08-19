import os
import time
import json
import wave
import queue
import tempfile
import threading
import sounddevice as sd

try:
    import webrtcvad
    import whisper
except Exception:
    pass


from typing import Any, Dict, Optional, List
from app.core.core import Core

"""
    Расширение для интеграции с Whisper

    Установка:
        pip install openai-whisper webrtcvad

    Опции:
        model (str)                       - модели (tiny, base, small, medium, large, turbo)
        device (str)                      - cpu или cuda
        fp16 (bool)                       - использовать FP16 (для CUDA)
        language (str)                    - язык распознавания (ru, en, auto)
        initial_prompt (str)              - подсказка модели (список терминов, имён и тд)

        temperature (float)               - температура генерации (0 = детерминированный вывод)
        beam_size (int)                   - ширина beam search (>0 включает beam search)
        best_of (int)                     - количество гипотез при сэмплинге (с temperature > 0)
        condition_on_previous_text (bool) - учитывать ли предыдущий контекст в длинных аудио
        word_timestamps (bool)            - включить генерацию таймкодов для каждого слова
        compression_ratio_threshold (f)   - порог сжатия (для фильтрации мусора)
        logprob_threshold (float)         - порог logprob для отбраковки сегмента
        no_speech_threshold (float)       - порог вероятности тишины

        vad (int)                         - агрессивность voice activity detection (0..3)
        samplerate (int)                  - частота дискретизации входного аудио
        channels (int)                    - количество каналов (обычно 1)
        block_ms (int)                    - длина блока в мс (10/20/30 для webrtcvad)
        max_phrase_silence_ms (int)       - сколько тишины ждать перед завершением фразы
        min_phrase_ms (int)               - минимальная длина фразы (короче = игнор)
        max_phrase_ms_cap (int)           - ограничение длины одной фразы (safety)

        output_dir (str)                  - директория для сохранения результатов
        autosave_txt (bool)               - сохранять текст в TXT
        autosave_srt (bool)               - сохранять субтитры в SRT
        autosave_vtt (bool)               - сохранять субтитры в VTT
        autosave_json (bool)              - сохранять результат и сегменты в JSON

        preload_on_start (bool)           - загружать модель при старте расширения

    Команды:
        шёпот распознай файл runtime/test.mp3 - транскрипция аудиофайла в текст (оставить язык оригинала)
        шёпот переведи аудио runtime/test.mp3" - перевод аудиофайла на английский
        шёпот распознай подробно runtime/test.mp3 - транскрипция с сохранением словарных таймкодов и JSON

        шёпот включи офлайн - запуск потокового распознавания с микрофона
        шёпот включи перевод офлайн - запуск потокового перевода (любой язык -> английский) в реальном времени
        шёпот выключи офлайн - остановка потокового распознавания/перевода

        шёпот язык ru - установка языка распознавания (ru, en, auto)
        шёпот подсказка голанг - подсказка с терминами/именами
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "whisper",

        "options": {
            "model": "tiny",
            "device": "cuda",
            "fp16": True,
            "language": "ru",
            "initial_prompt": "",
            "temperature": 0.0,
            "beam_size": 0,
            "best_of": 1,
            "condition_on_previous_text": True,
            "word_timestamps": False,
            "compression_ratio_threshold": 2.4,
            "logprob_threshold": -1.0,
            "no_speech_threshold": 0.6,
            "vad": 2,
            "samplerate": 16000,
            "channels": 1,
            "block_ms": 20,
            "max_phrase_silence_ms": 600,
            "min_phrase_ms": 400,
            "max_phrase_ms_cap": 15000,
            "output_dir": "./out/whisper",
            "autosave_txt": True,
            "autosave_srt": True,
            "autosave_vtt": False,
            "autosave_json": False,
            "preload_on_start": False,
        },

        "commands": {
            "шёпот распознай файл": _cmd_transcribe_file,
            "шёпот переведи аудио": _cmd_translate_file,
            "шёпот распознай подробно": _cmd_transcribe_file_verbose,
            "шёпот включи офлайн": _cmd_stream_on_transcribe,
            "шёпот включи перевод офлайн": _cmd_stream_on_translate,
            "шёпот выключи офлайн": _cmd_stream_off,
            "шёпот язык": _cmd_set_language,
            "шёпот подсказка": _cmd_set_prompt,
        },
    }

try:
    _model: Optional[whisper.Whisper] = None
except Exception:
    pass

_stream_on = threading.Event()
_stop_stream = threading.Event()
_audio_q: "queue.Queue[bytes]" = queue.Queue(maxsize=200)

_rec_thread: Optional[threading.Thread] = None
_worker_thread: Optional[threading.Thread] = None
_thread_lock = threading.Lock()

# Режим для стрима transcribe или translate
_stream_task: str = "transcribe"

def start(core: Core, manifest: Dict[str, Any]) -> None:
    try:
        opts = core.extension_options(__package__)
    except Exception:
        return

    if opts.get("preload_on_start"):
        try:
            _load_model(core)
            core.say("Whisper готов")
        except Exception:
            pass

"""
    Ленивая загрузка модели Whisper в _model
"""
def _load_model(core: Core) -> None:
    opts = core.extension_options(__package__)
    global _model
    if _model is not None:
        return
    try:
        _model = whisper.load_model(opts["model"], device=opts["device"])
    except Exception as e:
        core.print_error("[whisper] Ошибка загрузки модели", e)
        core.say("Не удалось загрузить модель")
        raise

"""
    SRT из сегментов Whisper
"""
def _segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    def ts(t: float) -> str:
        h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out: List[str] = []
    for i, seg in enumerate(segments, start=1):
        out.append(str(i))
        out.append(f"{ts(seg['start'])} --> {ts(seg['end'])}")
        out.append((seg.get('text') or '').strip())
        out.append("")
    return "\n".join(out)

"""
    VTT из сегментов Whisper
"""
def _segments_to_vtt(segments: List[Dict[str, Any]]) -> str:
    def ts(t: float) -> str:
        h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    out: List[str] = ["WEBVTT", ""]
    for seg in segments:
        out.append(f"{ts(seg['start'])} --> {ts(seg['end'])}")
        out.append((seg.get('text') or '').strip())
        out.append("")
    return "\n".join(out)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

"""
    Базовое имя для сохранения результатов
"""
def _basename_for_output(input_path: str, opts: Dict[str, Any]) -> str:
    outdir = opts.get("output_dir") or "./out"
    _ensure_dir(outdir)
    base = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(outdir, base)

"""
    Сохранить TXT, SRT, VTT, JSON
"""
def _save_outputs(base: str, text: str, segments: List[Dict[str, Any]], meta: Dict[str, Any], opts: Dict[str, Any]) -> None:
    if opts.get("autosave_txt"):
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(text + "\n")

    if opts.get("autosave_srt"):
        with open(base + ".srt", "w", encoding="utf-8") as f:
            f.write(_segments_to_srt(segments))

    if opts.get("autosave_vtt"):
        with open(base + ".vtt", "w", encoding="utf-8") as f:
            f.write(_segments_to_vtt(segments))

    if opts.get("autosave_json"):
        payload = {
            "text": text,
            "language": meta.get("language"),
            "task": meta.get("task"),
            # Могут содержать words, если word_timestamps=True
            "segments": segments,
        }
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

"""
    Сконструировать аргументы для model.transcribe
"""
def _build_whisper_kwargs(opts: Dict[str, Any], task: str) -> Dict[str, Any]:
    language_opt = opts.get("language")
    if language_opt and str(language_opt).lower() in ("auto", "none"):
        language_opt = None

    kw: Dict[str, Any] = {
        "task": task,
        "language": language_opt,
        "fp16": bool(opts.get("fp16")) and (opts.get("device") == "cuda"),
        "verbose": False,
        "temperature": float(opts.get("temperature", 0.0)),
        "condition_on_previous_text": bool(opts.get("condition_on_previous_text", True)),
        "word_timestamps": bool(opts.get("word_timestamps", False)),
        "initial_prompt": (opts.get("initial_prompt") or None),
        "compression_ratio_threshold": float(opts.get("compression_ratio_threshold", 2.4)),
        "logprob_threshold": float(opts.get("logprob_threshold", -1.0)),
        "no_speech_threshold": float(opts.get("no_speech_threshold", 0.6)),
    }

    beam_size = int(opts.get("beam_size", 0))
    best_of = int(opts.get("best_of", 1))

    if beam_size > 0:
        kw["beam_size"] = beam_size

    if best_of > 1:
        kw["best_of"] = best_of

    return kw

"""
    Сохранить PCM int16 mono во временный WAV и вернуть путь
"""
def _save_temp_wav(pcm_bytes: bytes, sr: int) -> str:

    f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    with wave.open(f.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm_bytes)
    return f.name

"""
    Транскрипция файла
"""
def _cmd_transcribe_file(core: Core, phrase: str) -> None:
    path = (phrase or "").strip().strip('"').strip("'")
    if not path or not os.path.exists(path):
        core.say("Файл не найден")
        return
    _transcribe_path(core, path, translate=False, force_verbose=False)

"""
    Перевод файла
"""
def _cmd_translate_file(core: Core, phrase: str) -> None:
    path = (phrase or "").strip().strip('"').strip("'")
    if not path or not os.path.exists(path):
        core.say("Файл не найден")
        return
    _transcribe_path(core, path, translate=True, force_verbose=False)

"""
    Распознать файл подробно: включить word_timestamps и JSON только для этого запуска
"""
def _cmd_transcribe_file_verbose(core: Core, phrase: str) -> None:
    path = (phrase or "").strip().strip('"').strip("'")
    if not path or not os.path.exists(path):
        core.say("Файл не найден")
        return
    _transcribe_path(core, path, translate=False, force_verbose=True)

"""
    Универсальная обработка файла с сохранениями
"""
def _transcribe_path(core: Core, path: str, translate: bool, force_verbose: bool) -> None:
    opts = core.extension_options(__package__)
    try:
        _load_model(core)

        task = "translate" if translate else "transcribe"
        kw = _build_whisper_kwargs(opts, task)

        # Форсируем подробный режим на один вызов (слово-таймкоды и JSON)
        if force_verbose:
            kw["word_timestamps"] = True

        result = _model.transcribe(path, **kw)

        text = (result.get("text") or "").strip()
        segments = result.get("segments") or []
        language = result.get("language")

        base = _basename_for_output(path, opts)
        meta = {"task": task, "language": language}

        # Если force_verbose - насильно включаем autosave_json
        save_json_orig = opts.get("autosave_json", False)
        if force_verbose:
            opts["autosave_json"] = True

        _save_outputs(base, text, segments, meta, opts)

        if force_verbose:
            opts["autosave_json"] = save_json_orig

        core.say("Готово")
        print(f"[WHISPER] task={task} language={language} -> {base}.*")
        print("\n[WHISPER]\n", text)

    except Exception as e:
        core.print_error("[whisper] Ошибка транскрипции файла", e)
        core.say("Ошибка")

def _cmd_stream_on_transcribe(core: Core, phrase: str) -> None:
    _stream_on_common(core, task="transcribe")


def _cmd_stream_on_translate(core: Core, phrase: str) -> None:
    _stream_on_common(core, task="translate")

"""
    Общий запуск стрима: транскрипция или перевод
"""
def _stream_on_common(core: Core, task: str) -> None:
    global _stream_task
    with _thread_lock:
        if _stream_on.is_set():
            core.say("Уже включён")
            return

        try:
            _load_model(core)
        except Exception:
            return

        while not _audio_q.empty():
            try:
                _audio_q.get_nowait()
            except queue.Empty:
                break

        _stream_task = task
        _stop_stream.clear()
        _stream_on.set()

        global _rec_thread, _worker_thread
        _rec_thread = threading.Thread(target=_rec_loop, args=(core,), daemon=True)
        _worker_thread = threading.Thread(target=_worker_loop, args=(core,), daemon=True)
        _rec_thread.start()
        _worker_thread.start()

        core.say("Whisper офлайн включён" + (" (перевод)" if task == "translate" else ""))

"""
    Остановить потоковое распознавание и корректно завершить потоки
"""
def _cmd_stream_off(core: Core, phrase: str) -> None:
    with _thread_lock:
        if not _stream_on.is_set():
            core.say("Уже выключен")
            return

        _stop_stream.set()
        _stream_on.clear()

        global _rec_thread, _worker_thread
        if _rec_thread and _rec_thread.is_alive():
            _rec_thread.join(timeout=1.5)
        if _worker_thread and _worker_thread.is_alive():
            _worker_thread.join(timeout=1.5)

        _rec_thread = None
        _worker_thread = None

        while not _audio_q.empty():
            try:
                _audio_q.get_nowait()
            except queue.Empty:
                break

        core.say("Whisper офлайн выключен")

"""
    Поток записи с микрофона
    Складывает сырые блоки PCM в очередь
"""
def _rec_loop(core: Core) -> None:
    opts = core.extension_options(__package__)
    blocksize = int(opts["samplerate"] * (opts["block_ms"] / 1000.0))

    def _cb(indata, frames, time_info, status):
        if _stop_stream.is_set():
            raise sd.CallbackStop()
        try:
            _audio_q.put_nowait(bytes(indata))
        except queue.Full:
            pass

    try:
        with sd.RawInputStream(
            samplerate=opts["samplerate"],
            blocksize=blocksize,
            dtype='int16',
            channels=opts["channels"],
            callback=_cb,
        ):
            while not _stop_stream.is_set():
                time.sleep(0.05)
    except Exception as e:
        core.print_error("[whisper] Ошибка аудиопотока", e)
        _stop_stream.set()

"""
    Поток обработки: VAD-сборка фраз + вызовы Whisper на готовых фразах
"""
def _worker_loop(core: Core) -> None:
    opts = core.extension_options(__package__)
    vad = webrtcvad.Vad(max(0, min(3, int(opts["vad"]))))
    block_bytes = int(opts["samplerate"] * (opts["block_ms"] / 1000.0)) * 2

    buf = bytearray()
    voiced = False
    last_voice_ts = 0.0
    phrase_start_ts = 0.0

    def is_voiced(pcm: bytes) -> bool:
        return vad.is_speech(pcm, opts["samplerate"])

    try:
        while not _stop_stream.is_set():
            try:
                chunk = _audio_q.get(timeout=0.1)
            except queue.Empty:
                # Завершение по тишине
                if voiced and (time.time() - last_voice_ts) * 1000 >= opts["max_phrase_silence_ms"]:
                    _flush_phrase(core, bytes(buf))
                    buf.clear()
                    voiced = False
                continue

            # Нормируем размер блока под VAD
            if len(chunk) != block_bytes:
                if len(chunk) > block_bytes:
                    chunk = chunk[:block_bytes]
                else:
                    chunk = chunk + b"\x00" * (block_bytes - len(chunk))

            if is_voiced(chunk):
                if not voiced:
                    phrase_start_ts = time.time()
                voiced = True
                last_voice_ts = time.time()
                buf.extend(chunk)

                # Принудительное ограничение длины одной фразы
                if (time.time() - phrase_start_ts) * 1000 >= int(opts["max_phrase_ms_cap"]):
                    _flush_phrase(core, bytes(buf))
                    buf.clear()
                    voiced = False
                    continue

            # Завершение по тишине (проверка сразу после обработки блока)
            if voiced and (time.time() - last_voice_ts) * 1000 >= opts["max_phrase_silence_ms"]:
                _flush_phrase(core, bytes(buf))
                buf.clear()
                voiced = False

        if buf:
            _flush_phrase(core, bytes(buf))

    except Exception as e:
        core.print_error("[whisper] Ошибка рабочего потока", e)
        _stop_stream.set()

"""
    Запуск Whisper на собранной фразе (stream)
"""
def _flush_phrase(core: Core, pcm_bytes: bytes) -> None:
    opts = core.extension_options(__package__)
    ms = int(len(pcm_bytes) / 2 / opts["samplerate"] * 1000)
    if ms < int(opts["min_phrase_ms"]):
        return

    path: Optional[str] = None
    try:
        path = _save_temp_wav(pcm_bytes, opts["samplerate"])
        task = _stream_task
        kw = _build_whisper_kwargs(opts, task)

        result = _model.transcribe(path, **kw)

        text = (result.get('text') or '').strip()
        language = result.get('language')
        if text:
            print(f"[WHISPER] task={task} lang={language}:", text)
            try:
                core.run_input_str(text)
            except Exception:
                pass

    except Exception as e:
        core.print_error("[whisper] Ошибка стрима", e)
    finally:
        try:
            if path and os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass

"""
    Установить язык
"""
def _cmd_set_language(core: Core, phrase: str) -> None:
    lang = (phrase or "").strip().lower()
    try:
        opts = core.extension_options(__package__)
        if lang in ("auto", "", "none"):
            opts["language"] = ""
            core.say("Whisper: язык - автоопределение")
        else:
            # Защита от случайного длинного текста
            if len(lang) > 5:
                core.say("Укажите код языка, например: ru, en, auto")
                return
            opts["language"] = lang
            core.say(f"Whisper: язык - {lang}")
    except Exception as e:
        core.print_error("[whisper] Не удалось установить язык", e)
        core.say("Ошибка")

"""
    Установить initial_prompt подсказку
"""
def _cmd_set_prompt(core: Core, phrase: str) -> None:
    prompt = (phrase or "").strip()
    try:
        opts = core.extension_options(__package__)
        opts["initial_prompt"] = prompt
        core.say("Whisper: подсказка сохранена")
    except Exception as e:
        core.print_error("[whisper] Не удалось установить подсказку", e)
        core.say("Ошибка")
