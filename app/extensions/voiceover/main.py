import logging

from typing import Any, Dict
from app.core.core import Core

"""
    Голосовая команда: Озвучивание текста

    Команды:
        озвучь|скажи <текст> - озвучить переданный текст
        буфер                - озвучить текст из буфера обмена

    Опции:
        wavBeforeGeneration: bool  - проигрывать звуковой сигнал перед озвучкой (полезно, если TTS может думать долго)
        wavPath: str               - путь к WAV-файлу сигнала
        usetts_engine_id_2: bool      - озвучивать вторым движком (say2), иначе основным (say)
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "Озвучивание текста",

        "options": {
            "wavBeforeGeneration": True,
            "wavPath": 'assets/audio/timer.wav',
            "usetts_engine_id_2": True,
        },

        "commands": {
            "озвучь|скажи": say,
            "буфер": say_clipboard,
        }
    }

logger = logging.getLogger(__name__)

def start(core: Core, manifest: Dict[str, Any]) -> None:
    pass

"""
    Озвучивает текст, переданный после команды
    Пример: "легион скажи привет" -> озвучит "привет"
"""
def say(core: Core, phrase: str):
    text = (phrase or "").strip()
    if not text:
        core.say2("Нечего сказать")
        return

    _beep_if_needed(core)
    _speak(core, text)

"""
    Озвучивает текст из буфера обмена
    Linux: требуется установленный xclip/xsel или wl-clipboard
    Windows/macOS: достаточно pip install pyperclip
"""
def say_clipboard(core: Core, phrase: str):
    text = None

    try:
        import pyperclip
        try:
            text = pyperclip.paste()
        except Exception as e:
            logger.exception("Ошибка при получении текста из буфера обмена через pyperclip: %s", e)
    except ImportError:
        logger.warning("Модуль pyperclip не установлен. Попробую системный fallback для Windows...")

    # Fallback для Windows без pyperclip (pywin32)
    if text is None:
        try:
            from sys import platform
            if platform == "win32":
                try:
                    import win32clipboard  # type: ignore
                    win32clipboard.OpenClipboard()
                    data = win32clipboard.GetClipboardData()
                    win32clipboard.CloseClipboard()
                    text = str(data) if data is not None else ""
                except ImportError:
                    logger.error("pyperclip не установлен и нет pywin32. Установите один из вариантов: pip install pyperclip или pip install pywin32")
                except Exception as e:
                    logger.exception("Ошибка при чтении буфера через win32clipboard: %s", e)
        except Exception:
            pass

    if not text:
        core.say2("Буфер обмена пуст или недоступен.")
        return

    text = text.strip()
    if not text:
        core.say2("В буфере обмена нет текста")
        return

    _beep_if_needed(core)
    _speak(core, text)

"""
    Проигрывает звуковой сигнал перед озвучкой, если это включено в настройках
"""
def _beep_if_needed(core: Core):
    opts = core.extension_options(__package__)
    if opts.get("wavBeforeGeneration", True):
        wav_path = opts.get("wavPath", "assets/audio/timer.wav")
        try:
            core.play_wav(wav_path)
        except Exception as e:
            logger.warning("Не удалось проиграть сигнал перед озвучкой (%s): %s", wav_path, e)

"""
    Озвучивает текст выбранным движком согласно опциям
"""
def _speak(core: Core, text: str):
    opts = core.extension_options(__package__)
    try:
        if opts.get("usetts_engine_id_2", True):
            core.say2(text)
        else:
            core.say(text)
    except Exception as e:
        logger.exception("Ошибка при озвучке текста: %s", e)
        core.say2("Ошибка при озвучке")
