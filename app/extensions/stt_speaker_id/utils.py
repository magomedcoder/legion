import os
import numpy as np
import soundfile as sf
import librosa
import webrtcvad
import re

from typing import List, Tuple, Optional

def safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Zа-яА-Я0-9_.\\/-]+", "_", name.strip())

def exists(path: Optional[str]) -> bool:
    return bool(path) and os.path.exists(path)

def resample_mono(path: str, target_sr: int) -> np.ndarray:
    y, sr = librosa.load(path, sr=target_sr, mono=True)
    if y.dtype != np.float32:
        y = y.astype(np.float32)
    return y

def frame_bytes(sig16: bytes, frame_ms: int, sr: int) -> int:
    samples_per_frame = sr * frame_ms // 1000
    return samples_per_frame * 2

def to_pcm16(y: np.ndarray) -> bytes:
    y16 = np.clip(y, -1.0, 1.0)
    y16 = (y16 * 32767.0).astype(np.int16)
    return y16.tobytes()

def extract_path(phrase: str) -> Optional[str]:
    if not phrase:
        return None
    m = re.search(r"\"([^\"]+)\"", phrase)
    if m:
        return m.group(1)
    parts = phrase.strip().split()
    return parts[0] if parts else None

def extract_name_after_keyword(phrase: str, keyword: str = "как") -> Optional[str]:
    if not phrase:
        return None
    idx = phrase.lower().find(f" {keyword} ")
    if idx >= 0:
        return phrase[idx + len(keyword) + 2:].strip().strip('"').strip("'")
    return None

def dur_seconds(path: str) -> float:
    try:
        info = sf.info(path)
        if info.samplerate:
            return float(info.frames) / float(info.samplerate)
    except Exception:
        pass
    try:
        y, sr = librosa.load(path, sr=None, mono=True)
        return float(len(y) / (sr if sr else 1))
    except Exception:
        return 0.0

def split_by_vad(y: np.ndarray, sr: int, vad_frame_ms: int, vad_aggr: int) -> List[Tuple[int, int]]:
    vad = webrtcvad.Vad(int(vad_aggr))
    pcm = to_pcm16(y)
    step = frame_bytes(pcm, vad_frame_ms, sr)

    frames = []
    for off in range(0, len(pcm) - step + 1, step):
        frames.append((off, off + step))
    voiced = []

    for (a, b) in frames:
        is_voiced = vad.is_speech(pcm[a:b], sample_rate=sr)
        voiced.append(is_voiced)

    intervals = []
    i = 0
    while i < len(voiced):
        if voiced[i]:
            j = i + 1
            while j < len(voiced) and voiced[j]:
                j += 1
            st_b = max(0, (i - 1) * step)
            en_b = min(len(pcm), (j + 1) * step)
            st = st_b // 2
            en = en_b // 2
            intervals.append((st, en))
            i = j
        else:
            i += 1
    return intervals
