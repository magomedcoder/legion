import shutil
import subprocess
from typing import List, Dict, Any

from app.core.core import Core

"""
    Расширение для получения температуры GPU NVIDIA через nvidia-smi

    Команда:
        "температура видеокарты" - температура и название GPU

    Опции:
        gpu_name_filter (str|None)  - фильтр по имени GPU (регистронезависимо). Пусто/None = без фильтра
        gpu_index (int|None)        - индекс GPU (0..N-1)
        prefer_max_when_many (bool) - если много устройств: True -> сообщать самую горячую, False -> перечислять все
        say_answer (bool)           - озвучивать ли ответ через TTS
        alert_temp_threshold (int)  - порог температуры для предупреждения

"""
def manifest() -> Dict[str, Any]:
    return {
        "name": "Температура видеокарты",

        "options": {
            "gpu_name_filter": "Quadro RTX 6000",
            "gpu_index": None,
            "prefer_max_when_many": True,
            "alert_temp_threshold": 100
        },

        "commands": {
            "температура видеокарты": _cmd_gpu_temp,
        },
    }

def start(core: Core, manifest: Dict[str, Any]) -> None:
    pass

def _cmd_gpu_temp(core: Core, phrase: str):
    opts = core.extension_options(__package__)

    if not shutil.which("nvidia-smi"):
        core.say("nvidia-smi не найдена")
        return

    try:
        gpus = _query_gpus()
    except Exception as e:
        core.say(f"Ошибка запроса nvidia-smi: {e}")
        return

    if not gpus:
        core.say("GPU не обнаружены")
        return

    gpu_index = opts.get("gpu_index", None)
    name_filter = (opts.get("gpu_name_filter") or "").strip().lower()

    selected: List[Dict] = []

    if isinstance(gpu_index, int):
        for g in gpus:
            if g.get("index") == gpu_index:
                selected = [g]
                break
        if not selected:
            core.say("Подходящая видеокарта не найдена")
            return
    else:
        if name_filter:
            selected = [g for g in gpus if name_filter in g.get("name", "").lower()]
        else:
            selected = gpus
        if not selected:
            core.say("Подходящая видеокарта не найдена")
            return

    if len(selected) == 1:
        g = selected[0]
        temp = g.get("temp")
        msg = f"{g.get('name')}: {temp}"

        threshold = opts.get("alert_temp_threshold")
        if isinstance(threshold, (int, float)) and temp >= threshold:
            msg += "ВНИМАНИЕ: высокая температура!"

        core.say(f"Текущая температура {msg}".strip())
        return

    if bool(opts.get("prefer_max_when_many", True)):
        g = max(selected, key=lambda x: x.get("temp", -273))
        msg = "{name}: {temp}".format(name=g.get("name"), temp=g.get("temp"))
        core.say(f"Текущая температура {msg}".strip())
        return

    items = ["{name}: {temp}".format(name=g.get("name"), temp=g.get("temp")) for g in selected]
    joined = (", ").join(items)
    core.say(f"Текущая температура {joined}".strip())

def _query_gpus() -> List[Dict]:
    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,name,temperature.gpu", "--format=csv,noheader,nounits"], 
        capture_output=True, 
        text=True, 
        check=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    gpus: List[Dict] = []
    for ln in lines:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0])
            name = ", ".join(parts[1:-1])
            temp = int(parts[-1])
            gpus.append({"index": idx, "name": name, "temp": temp})
        except Exception:
            continue

    return gpus
