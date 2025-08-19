import os
import numpy as np

from typing import Dict, List
from .utils import safe_name

class Store:
    def __init__(self, root: str):
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    def path_for(self, name: str) -> str:
        base = safe_name(name).lower()
        return os.path.join(self.root, f"{base}.npy")

    def save(self, name: str, emb: np.ndarray):
        p = self.path_for(name)
        if os.path.exists(p):
            prev = np.load(p)
            emb = (prev + emb) / 2.0
        np.save(p, emb.astype(np.float32))

    def list(self) -> List[str]:
        return sorted([os.path.splitext(f)[0] for f in os.listdir(self.root) if f.endswith(".npy")])

    def load_all(self) -> Dict[str, np.ndarray]:
        out = {}
        for f in os.listdir(self.root):
            if f.endswith(".npy"):
                out[os.path.splitext(f)[0]] = np.load(os.path.join(self.root, f))
        return out

    def delete(self, name: str) -> bool:
        p = self.path_for(name)
        if os.path.exists(p):
            os.remove(p)
            return True
        return False

    def clear(self):
        for f in os.listdir(self.root):
            if f.endswith(".npy"):
                try:
                    os.remove(os.path.join(self.root, f))
                except Exception:
                    pass
