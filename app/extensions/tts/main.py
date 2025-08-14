import pyttsx3

from app.core.core import Core
from .rhvoice import RHVClient

"""
    TTS через RHVoice, pyttsx3 и консоль (для отладки)

    tts:
        1. init - инициализация движка
        2. say - озвучка напрямую
        3. to_wav_file - озвучка в файл
"""

def manifest():
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

def start(core: Core, manifest: dict):
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
    core.ttsrhvoice = RHVClient()

"""
    Озвучивание текста с сохранением результата в WAV-файл
"""
def rhvoice_to_wav_file(core: Core, text_to_speech: str, wavfile: str):
    opts = core.extension_options(__package__)
    core.ttsrhvoice.to_file(
        filename=wavfile,
        text=text_to_speech,
        voice=opts.get("rhvoice_voice_id"),
    )

"""
    Инициализация pyttsx3
"""
def pyttsx_init(core: Core):
    opts = core.extension_options(__package__)
    core.ttsEngine = pyttsx3.init()
    voices = core.ttsEngine.getProperty("voices")
    # if 0 <= opts["sys_id"] < len(voices):
    #     core.ttsEngine.setProperty("voice", voices[opts["sys_id"]].id)
    # else:
    #     core.ttsEngine.setProperty("voice", "russian")
    core.ttsEngine.setProperty("voice", "russian")
    core.ttsEngine.setProperty("volume", 1.0)

"""
    Озвучивание текста напрямую
"""
def pyttsx_say(core: Core, text_to_speech: str):
    core.ttsEngine.say(str(text_to_speech))
    core.ttsEngine.runAndWait()

"""
    Озвучивание текста с сохранением результата в WAV-файл
"""
def pyttsx_to_wav_file(core: Core, text_to_speech: str, wavfile: str):
    core.ttsEngine.save_to_file(str(text_to_speech), wavfile)
    core.ttsEngine.runAndWait()