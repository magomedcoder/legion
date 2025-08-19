from typing import Any, Dict, Optional

from app.core.core import Core
from .speaker_service import SpeakerService
from .utils import extract_name_after_keyword, exists, extract_path

"""
    Speaker ID + простая диаризация

    pip install speechbrain==0.5.16 numpy scikit-learn librosa soundfile webrtcvad
    git clone https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb app/models/spkrec-ecapa-voxceleb

    Опции:
        model_dir        - модель SpeechBrain ECAPA
        store_dir        - эмбеддинги npy
        sr               - частота ресемплинга для эмбеддингов (16000)
        enroll_min_sec   - длительность записи для энролла в мин(1.0)
        diar_window_sec  - окно для эмбеддинга при диаризации (1.5)
        diar_hop_sec     - шаг окон при диаризации (0.75)
        vad_frame_ms     - размер фрейма для VAD (10 | 20 | 30)
        vad_aggr         - агрессивность VAD 0..3 (чем выше тем строже)

    Команды:
        запомни голос runtime/test.mp3 как мда
        кто на записи runtime/test.mp3
        список голосов
        забудь голос мда
        очисти голоса
        диаризация файла runtime/test.mp3
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "Speaker ID + простая диаризация",

        "options": {
            "model_dir": "./app/models/spkrec-ecapa-voxceleb",
            "model_tmp_dir": "./runtime/models/stt_speaker_id",
            "store_dir": "./runtime/speaker-id-voices",
            "sr": 16000,
            "enroll_min_sec": 1.0,
            "diar_window_sec": 1.5,
            "diar_hop_sec": 0.75,
            "vad_frame_ms": 20,
            "vad_aggr": 2
        },

        "commands": {
            "запомни голос": _cmd_enroll,
            "кто на записи": _cmd_identify,
            "список голосов": _cmd_list,
            "забудь голос": _cmd_forget,
            "очисти голоса": _cmd_clear,
            "диаризация файла": _cmd_diarize
        }
    }

_svc: Optional[SpeakerService] = None

def start(core: Core, manifest: Dict[str, Any]) -> None:
    global _svc
    try:
        _svc = SpeakerService(manifest["options"])
    except Exception as e:
        print("Ошибка инициализации stt_speaker_id: " + str(e))
        return

def _cmd_enroll(core, phrase: str):
    if _svc is None:
        core.say("Распознавание голосов недоступно")
        return

    path = extract_path(phrase)
    if not exists(path):
        core.say('Не нашла файл. Скажи: запомни голос из файла путь как имя')
        return

    name = extract_name_after_keyword(phrase, "как")
    if not name:
        core.say("Скажи, как назвать этот голос. пример: как мда")
        return

    ok, msg, emb = _svc.enroll(path)
    if not ok or emb is None:
        core.say("Не получилось: " + msg)
        return

    _svc.store.save(name, emb)
    core.say(f'Голос «{name}» сохранён')

def _cmd_identify(core, phrase: str):
    if _svc is None:
        core.say("Распознавание голосов недоступно")
        return

    path = extract_path(phrase)
    if not exists(path):
        core.say('Не нашла файл. Скажи: кто на записи путь')
        return

    name, sim = _svc.identify(path)
    if name is None:
        core.say("База голосов пуста или не удалось распознать речь")
        return

    core.say(f"Похоже, это {name}. Сходство {sim:.2f}")

def _cmd_list(core, phrase: str):
    if _svc is None:
        core.say("Распознавание голосов недоступно")
        return

    lst = _svc.store.list()
    core.say("Сохранённых голосов нет" if not lst else "Сохранённые голоса: " + ", ".join(lst))

def _cmd_forget(core, phrase: str):
    if _svc is None:
        core.say("Распознавание голосов недоступно")
        return

    name = (phrase or "").strip().strip('"').strip("'")
    if not name:
        core.say("Скажи: забудь голос Имя")
        return

    core.say(f"Голос {name} удалён." if _svc.store.delete(name) else f"Голос {name} не найден")

def _cmd_clear(core, phrase: str):
    if _svc is None:
        core.say("Распознавание голосов недоступно")
        return

    _svc.store.clear()
    core.say("Все голоса очищены")

def _cmd_diarize(core, phrase: str):
    if _svc is None:
        core.say("Диаризация недоступна")
        return
    
    path = extract_path(phrase)
    if not exists(path):
        core.say('Не нашла файл. Скажи: диаризация файла путь')
        return
    
    segs = _svc.diarize(path)
    parts = [f"спикер {spk} с {s:.1f} по {e:.1f}" for (s, e, spk) in segs[:6]]
    if len(segs) > 6:
        parts.append("и другие сегме")

    core.say("; ".join(parts) if parts else "Не удалось сегментировать")
