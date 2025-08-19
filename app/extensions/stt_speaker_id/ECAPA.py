import os
import numpy as np
from .utils import resample_mono
import torch

try:
    from speechbrain.pretrained import EncoderClassifier
except Exception:
    pass

class ECAPA:
    def __init__(self, model_dir: str, model_tmp_dir: str, sr: int):
        if not os.path.isdir(model_dir):
            raise RuntimeError(f"Папка модели не найдена: {model_dir}")

        os.environ.setdefault("HF_HUB_OFFLINE", "1")

        self.clf = EncoderClassifier.from_hparams(
            source=model_dir, 
            savedir=model_tmp_dir,
            run_opts={"device": "cpu"},
        )
        self.sr = int(sr)

    def embed_signal(self, y: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            t = torch.from_numpy(y).float().unsqueeze(0)
            emb = self.clf.encode_batch(t).squeeze(0).mean(dim=0).cpu().numpy()
        return emb

    def embed_file(self, path: str) -> np.ndarray:
        y = resample_mono(path, self.sr)
        return self.embed_signal(y)
