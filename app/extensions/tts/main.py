import pyttsx3

from typing import Any, Dict
from app.core.core import Core
from app.utils.rhvoice import RHVClient

"""
    TTS через RHVoice, pyttsx3 и консоль (для отладки)

    tts:
        1. init - инициализация движка
        2. say - озвучка напрямую
        3. to_wav_file - озвучка в файл
"""

def manifest() -> Dict[str, Any]:
    return {
        "name": "TTS через pyttsx3",

        "options": {
            "sys_id": 0,
            "rhvoice_voice_id": "anna"
        },

        "tts": {
            "console": (console_init, console_say),

            "pyttsx": (pyttsx_init, pyttsx_say, pyttsx_to_wav_file),
            "rhvoice": (rhvoice_init, None, rhvoice_to_wav_file)
        }
    }

def start(core: Core, manifest: Dict[str, Any]) -> None:
    pass


"""
    Инициализация Console
"""
def console_init(core: Core):
    pass

"""
    Ввод
"""
def console_say(core: Core, text_to_speech: str):
    print(f"TTS(console): {text_to_speech}")


"""
    Инициализация RHVoice
"""
def rhvoice_init(core: Core):
    core.tts_rhvoice = RHVClient()

"""
    Озвучивание текста с сохранением результата в WAV-файл
"""
def rhvoice_to_wav_file(core: Core, text_to_speech: str, wavfile: str):
    opts = core.extension_options(__package__)
    core.tts_rhvoice.to_file(filename=wavfile, text=text_to_speech, voice=opts.get("rhvoice_voice_id"))

"""
    Инициализация pyttsx3
"""
def pyttsx_init(core: Core):
    core.tts_engine = pyttsx3.init()
    core.tts_engine.setProperty("voice", "russian")
    core.tts_engine.setProperty("volume", 1.0)

"""
    Озвучивание текста напрямую
"""
def pyttsx_say(core: Core, text_to_speech: str):
    core.tts_engine.say(str(text_to_speech))
    core.tts_engine.runAndWait()

"""
    Озвучивание текста с сохранением результата в WAV-файл
"""
def pyttsx_to_wav_file(core: Core, text_to_speech: str, wavfile: str):
    core.tts_engine.save_to_file(str(text_to_speech), wavfile)
    core.tts_engine.runAndWait()
