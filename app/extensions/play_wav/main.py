import os

import numpy

try:
    from audioplayer import AudioPlayer
except Exception:
    pass

try:
    import sounddevice as sound_device
    import soundfile as sound_file
except Exception:
    pass

from app.core.core import Core

"""
    Расширение для воспроизведения WAV-файлов с использованием библиотек
"""

def manifest():
    return {
        "name": "Воспроизведение WAV",

        "play_wav": {
            "audioplayer": (init, play_wav_audioplayer),
            "sounddevice": (init, play_wav_sounddevice)
        }
    }

def start(core: Core, manifest: dict):
    pass

def init(core: Core):
    pass

"""
    Проигрывает WAV-файл с использованием библиотеки audioplayer
"""
def play_wav_audioplayer(core: Core, wav_file: str):
    if not os.path.exists(wav_file):
        print(f"[Play wav audioplayer] Файл не найден: {wav_file}")
        return
    AudioPlayer(wav_file).play(block=True)

"""
    Проигрывает WAV-файл с использованием библиотеки sounddevice
"""
def play_wav_sounddevice(core: Core, wav_file: str):
    filename = os.path.dirname(__file__) + "/../" + wav_file
    data_set, fsample = sound_file.read(filename, dtype = 'float32')
    zeros = numpy.zeros((5000,))
    data_set_new = numpy.concatenate((data_set,zeros))
    sound_device.play(data_set_new, fsample)
    status = sound_device.wait()
    
    return
