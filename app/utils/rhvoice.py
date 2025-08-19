import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List

class RHVClient:
    def __init__(self):
        self.bin = shutil.which("RHVoice-test")
        if not self.bin:
            raise RuntimeError("Не найден RHVoice")

        self.voices_info: Dict[str, Dict] = self._discover_voices()
        self.voices: List[str] = sorted(self.voices_info.keys())

    def _discover_voices(self) -> Dict[str, Dict]:
        voices = {}
        for base in [Path("/usr/share/RHVoice/voices"), Path("/usr/local/share/RHVoice/voices"), Path.home() / ".local/share/RHVoice/voices"]:
            if not base.is_dir():
                continue
            for d in base.iterdir():
                if d.is_dir():
                    vid = d.name
                    voices.setdefault(vid, {"path": str(d)})
        return voices

    def to_file(self, filename: str, text: str, voice: str):
        if voice not in self.voices_info:
            pass

        proc = subprocess.run(
            [self.bin, "-p", voice, "-o", filename],
            input=text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0 or not os.path.isfile(filename):
            raise RuntimeError(f"RHVoice завершился с ошибкой ({proc.returncode}). "f"stderr:\n{proc.stderr}")