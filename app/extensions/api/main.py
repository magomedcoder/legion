import traceback
from typing import Optional
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

def manifest():
    return {
        "name": "API",

        "options": {
            "model_path": "./app/models/vosk"
        }
    }

def start(core: Core, manifest: dict):
    app: Optional[FastAPI] = getattr(core, "fastapi_app", None)
    if app is None:
        return manifest
    
    opts = manifest["options"]

    attach_rest(core, app)

    try:
        model_path: str = opts["model_path"]
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
