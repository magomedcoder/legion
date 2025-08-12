import os
import traceback
from typing import Any, Dict, Optional
from fastapi import FastAPI
from app.core.core import Core
from app.utils.fastapi_utils_tasks import repeat_every
from .models import *
from .rest import attach_rest
from .ws import attach_ws
from vosk import Model

"""
    Расширение регистрирует HTTP и WebSocket, если в core.fastapi_app передан экземпляр FastAPI

    Опции:
        model_path - путь к модели Vosk
"""

modname = os.path.basename(__package__)[12:]

def start(core: Core):
    manifest = {
        "name": "API",

        "options": {
            "model_path": "./app/models/vosk"
        }
    }

    app: Optional[FastAPI] = getattr(core, "fastapi_app", None)
    if app is None:
        return manifest
    
    cfg = get_opts(core, modname, manifest["options"])

    attach_rest(core, app)

    try:
        model_path: str = cfg["model_path"]
        model = Model(model_path)
        attach_ws(core, app, model)
    except Exception:
        traceback.print_exc()
        core.print_red("[api] Не удалось инициализировать модель Vosk")

    # Периодический апдейт таймеров
    @app.on_event("startup")
    @repeat_every(seconds=2)
    async def _update_timers_job():
        core.update_timers()

    return manifest

def get_opts(core: Core, extension_name: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    saved = core.extension_options(extension_name) or {}
    return {**defaults, **saved}