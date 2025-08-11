import logging
import os

import app.lib.lingua_franca

from app.core.core import Core

"""
    Основные настройки

    Опции
        useTTSCache (bool)- кэшировать озвучку текста (увеличивает использование диска при смене голосов кэш может устаревать)
        ttsEngineId (str) - id основного движка TTS на сервере
        ttsEngineId2 (str) - id дополнительного TTS-движка, который всегда работает локально на машине с ассистентом
        playWavEngineId (str) - id движка воспроизведения звука (например, "audioplayer", "sounddevice")
        linguaFrancaLang (str) - язык для библиотеки lingua-franca (преобразование чисел в текст)
        voiceAssNames (str) - имена, по которым ассистент будет распознавать обращение. Несколько имён разделяются символом |
        replyNoCommandFound (str) - ответ, если команда не распознана
        replyNoCommandFoundInContext (str) - ответ, если команда не распознана в контексте диалога
        contextDefaultDuration (int) - время (в секундах), в течение которого сохраняется контекст
        contextRemoteWaitForCall (bool) - (PRO) для режима Web API: ждать ли сигнала от клиента о завершении проигрывания
        fuzzyThreshold (float) - (PRO) порог уверенности для нечеткого распознавания команд
        voiceAssNameRunCmd (dict) - словарь автодобавления префиксов при обнаружении имени ассистента
        logPolicy (str) - политика вывода распознанной речи в консоль: all - выводить всегда, cmd - только если это команда, none - не выводить
        log_console (bool) - включить/выключить вывод логов в консоль
        log_console_level (str) - уровень логирования консоли (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file (bool) - включить/выключить вывод логов в файл
        log_file_level (str) - уровень логирования для лог-файла
        log_file_name (str) - имя файла для логов
        normalization_engine (str) - движок нормализации текста для TTS
            "default" - базовая подготовка текста
            Рекомендуется "runorm" для лучшего качества
        plugin_types (str) - какие типы плагинов загружать
"""


def start(core: Core):
    manifest = {
        "name": "Основные настройки",

        "options": {
            "useTTSCache": False,
            "ttsEngineId": "pyttsx",
            "ttsEngineId2": "",
            "playWavEngineId": "audioplayer",
            "linguaFrancaLang": "ru",
            "voiceAssNames": "легион",
            "replyNoCommandFound": "Извини, я не поняла",
            "replyNoCommandFoundInContext": "Не поняла...",
            "contextDefaultDuration": 10,
            "contextRemoteWaitForCall": False,
            "fuzzyThreshold": 0.5,
            "voiceAssNameRunCmd": {},
            "logPolicy": "cmd",
            "log_console": True,
            "log_console_level": "WARNING",
            "log_file": False,
            "log_file_level": "DEBUG",
            "log_file_name": "/runtime/log",
            "normalization_engine": "default",
            "plugin_types": "default",
        },

    }
    return manifest

def start_with_options(core: Core, manifest: dict):
    options = manifest["options"]

    # Имена и команды активации
    core.voiceAssNames = options["voiceAssNames"].split("|")
    core.voiceAssNameRunCmd = options["voiceAssNameRunCmd"]

    # Движки
    core.ttsEngineId = options["ttsEngineId"]
    core.ttsEngineId2 = options["ttsEngineId2"]
    core.playWavEngineId = options["playWavEngineId"]
    core.logPolicy = options["logPolicy"]

    # Контекст
    core.contextDefaultDuration = options["contextDefaultDuration"]
    core.contextRemoteWaitForCall = options["contextRemoteWaitForCall"]

    # Кэш TTS
    os.makedirs(core.tmpdir, exist_ok=True)
    core.useTTSCache = options["useTTSCache"]
    os.makedirs(core.tts_cache_dir, exist_ok=True)
    os.makedirs(os.path.join(core.tts_cache_dir, core.ttsEngineId), exist_ok=True)

    # Язык для чисел
    app.lib.lingua_franca.load_language(options["linguaFrancaLang"])

    # Нормализация
    core.normalization_engine = options["normalization_engine"]
    if core.normalization_engine == "default":
        core.normalization_engine = "prepare"

    # Типы плагинов
    plugin_types = options["plugin_types"]
    if plugin_types == "default":
        plugin_types = "classic"

    core.plugin_types = plugin_types.replace(" ", "").split(",")

    # Логирование
    core.log_console = options["log_console"]
    core.log_console_level = options["log_console_level"]
    core.log_file = options["log_file"]
    core.log_file_level = options["log_file_level"]
    core.log_file_name = options["log_file_name"]

    if core.log_console or core.log_file:
        # Сбрасываем старые обработчики, чтобы избежать дублирования логов
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Общий уровень - минимальный из двух
        root_logger.setLevel(min(core.log_console_level, core.log_file_level))

        if core.log_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(core.log_console_level)
            console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            root_logger.addHandler(console_handler)

        if core.log_file:
            file_handler = logging.FileHandler(core.log_file_name)
            file_handler.setLevel(core.log_file_level)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            root_logger.addHandler(file_handler)

        logger = logging.getLogger(__name__)
        if core.log_console:
            logger.info("Вывод логов в консоль включён")

        if core.log_file:
            logger.info("Вывод логов в файл включён")

    return manifest