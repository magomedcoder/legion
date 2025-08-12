import os

from app.core.core import Core

"""
    TTS консоль (для отладки)
"""
modname = os.path.basename(__package__)[12:]

def start(core: Core):
    manifest = {
        "name": "TTS консоль (для отладки)",

        "tts": {
            "console": (init, say)
        }
    }
    return manifest

def init(core: Core):
    pass

def say(core: Core, text_to_speech: str):
    print(f"TTS(console): {text_to_speech}")