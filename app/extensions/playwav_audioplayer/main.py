import os

from audioplayer import AudioPlayer

from app.core.core import Core

"""
    Расширение для воспроизведения WAV-файлов с использованием библиотеки audioplayer
"""

def manifest():
    return {
        "name": "Воспроизведение WAV (audioplayer)",

        "playwav": {
            "audioplayer": (init, play_wav)
        }
    }

def start(core: Core, manifest: dict):
    pass

def init(core: Core):
    pass

"""
    Проигрывает WAV-файл до конца
"""
def play_wav(core: Core, wav_file: str):
    if not os.path.exists(wav_file):
        print(f"[PlayWav audioplayer] Файл не найден: {wav_file}")
        return
    AudioPlayer(wav_file).play(block=True)