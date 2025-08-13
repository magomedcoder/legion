from app.core.core import Core

"""
    TTS консоль (для отладки)
"""

def manifest():
    return {
        "name": "TTS консоль (для отладки)",

        "tts": {
            "console": (init, say)
        }
    }

def start(core: Core, manifest: dict):
    pass

def init(core: Core):
    pass

def say(core: Core, text_to_speech: str):
    print(f"TTS(console): {text_to_speech}")