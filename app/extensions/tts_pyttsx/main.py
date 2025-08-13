import pyttsx3

from app.core.core import Core

"""
    TTS через библиотеку pyttsx3
"""

def manifest():
    return {
        "name": "TTS через pyttsx3",

        "options": {
            "sysId": 0
        },

        "tts": {
            # Кортеж:
            # 1. init - инициализация движка
            # 2. say - озвучка напрямую
            # 3. to_wav_file - озвучка в файл
            "pyttsx": (init, say, to_wav_file)
        }
    }

def start(core: Core, manifest: dict):
    pass

"""
    Инициализация pyttsx3 и настройка параметров голоса
"""
def init(core: Core):
    options = core.extension_options(__package__)
    core.ttsEngine = pyttsx3.init()
    voices = core.ttsEngine.getProperty("voices")
    # if 0 <= options["sysId"] < len(voices):
    #     core.ttsEngine.setProperty("voice", voices[options["sysId"]].id)
    # else:
    #     core.ttsEngine.setProperty("voice", "russian")
    core.ttsEngine.setProperty("voice", "russian")
    core.ttsEngine.setProperty("volume", 1.0)

"""
    Озвучивание текста напрямую (без сохранения в файл)
"""
def say(core: Core, text_to_speech: str):
    core.ttsEngine.say(str(text_to_speech))
    core.ttsEngine.runAndWait()

"""
    Озвучивание текста с сохранением результата в WAV-файл
"""
def to_wav_file(core: Core, text_to_speech: str, wavfile: str):
    core.ttsEngine.save_to_file(str(text_to_speech), wavfile)
    core.ttsEngine.runAndWait()