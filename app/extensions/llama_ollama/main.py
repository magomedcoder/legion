import os
import json
import traceback
from typing import Any, Dict

import requests

from app.core.core import Core

"""
    Расширение для интеграции с моделью Llama через Ollama API

    Установка и запуск Ollama с моделью Llama:
        curl -fsSL https://ollama.com/install.sh | sh
        ollama pull llama3.1
        ollama serve

    Опции:
        ollama_host (str)   - адрес Ollama API (по умолчанию http://127.0.0.1:11434)
        model (str)         - модель
        temperature (float) - параметр генерации (0–1, выше = более креативно)
        top_p (float)       - параметр nucleus sampling (0–1)
        max_tokens (int)    - ограничение на количество токенов (0/None = без ограничения)
        stop (list)         - список стоп-токенов
        system_prompt (str) - системная инструкция для модели
        say_answer (bool)   - озвучивать ли ответ TTS

"""

modname = os.path.basename(__package__)[12:]

def start(core: Core):
    manifest = {
        "name": "Llama 3.1 (Ollama)",

        "options": {
            "ollama_host": "http://127.0.0.1:11434",
            "model": "llama3.1",
            "temperature": 0.6,
            "top_p": 0.95,
            "max_tokens": 512,
            "stop": [],
            "system_prompt": "Отвечайте кратко на том же языке, на котором обращается пользователь",
            "say_answer": True,
        },

        "commands": {
            "лама": ask_llama,
        }
    }
    return manifest

def _get_opts(core: Core, extension_name: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    saved = core.extension_options(extension_name) or {}
    return {**defaults, **saved}

def _post_ollama_generate(host: str, payload: Dict[str, Any]):
    url = f"{host.rstrip('/')}/api/generate"
    with requests.post(url, json=payload, stream=True, timeout=(5, 600)) as r:
        r.raise_for_status()
        full_text = []
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            chunk = obj.get("response")
            if chunk:
                full_text.append(chunk)
            if obj.get("done"):
                break
        return "".join(full_text).strip()

def ask_llama(core: Core, phrase: str):
    try:
        cfg = _get_opts(core, modname, start(core)["options"])

        query = (phrase or "").strip()
        if not query:
            core.say("Скажи фразу после команды, например: «лама как погода на марсе ?»")
            return

        payload = {
            "model": cfg["model"],
            "prompt": query,
            "stream": True,
            "options": {
                "temperature": cfg.get("temperature", 0.6),
                "top_p": cfg.get("top_p", 0.95),
            },
            "system": cfg.get("system_prompt") or None,
        }

        max_tokens = cfg.get("max_tokens")
        if isinstance(max_tokens, int) and max_tokens > 0:
            payload["options"]["num_predict"] = max_tokens

        stop = cfg.get("stop") or []
        if isinstance(stop, list) and stop:
            payload["options"]["stop"] = stop

        answer = _post_ollama_generate(cfg["ollama_host"], payload)

        if not answer:
            core.say("Ответ пустой. Возможно, модель не запущена или вернула пустой результат")
            return

        if cfg.get("say_answer", True):
            core.say(answer)
        else:
            print(f"[llama] {answer}")
            core.lastSay = answer

    except requests.exceptions.ConnectionError:
        core.print_red("[llama] Нет соединения с Ollama")
        core.say("Не получается подключиться к серверу модели")
    except requests.exceptions.HTTPError as e:
        core.print_red(f"[llama] HTTP ошибка: {e}")
        core.say("Модель вернула ошибку")
    except Exception as e:
        traceback.print_exc()
        core.print_red(f"[llama] Неожиданная ошибка: {e}")
        core.say("Произошла ошибка при обращении к модели")
