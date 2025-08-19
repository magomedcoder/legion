import numpy as np
from typing import List, Tuple, Optional
from .ECAPA import ECAPA
from .store import Store
from .utils import dur_seconds, split_by_vad, resample_mono, split_by_vad

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import AgglomerativeClustering
except Exception:
    pass

class SpeakerService:
    def __init__(self, opts: dict):
        self.store = Store(opts.get("store_dir"))
        self.sr = int(opts.get("sr"))
        self.enroll_min_sec = float(opts.get("enroll_min_sec"))
        self.diar_win = float(opts.get("diar_window_sec"))
        self.diar_hop = float(opts.get("diar_hop_sec"))
        self.vad_frame_ms = int(opts.get("vad_frame_ms"))
        self.vad_aggr = int(opts.get("vad_aggr"))
        self.ecapa = ECAPA(model_dir=opts.get("model_dir"), model_tmp_dir=opts.get("model_tmp_dir"), sr=self.sr)

    def enroll(self, path: str) -> Tuple[bool, str, Optional[np.ndarray]]:
        dur = dur_seconds(path)
        if dur < self.enroll_min_sec:
            return False, f"Слишком короткая запись ({dur:.2f} c). Нужно {self.enroll_min_sec:.2f} c", None

        y = resample_mono(path, self.sr)
        ivals = split_by_vad(y, self.sr, self.vad_frame_ms, self.vad_aggr)
        if not ivals:
            return False, "Не обнаружена речь на записи", None

        embs = []
        for (st, en) in ivals:
            seg = y[st:en]
            if len(seg) / self.sr < 0.3:
                continue
            embs.append(self.ecapa.embed_signal(seg))
        if not embs:
            return False, "Слишком мало речи для эталона", None
        emb_mean = np.vstack(embs).mean(axis=0)
        return True, "OK", emb_mean


    def identify(self, path: str) -> Tuple[Optional[str], Optional[float]]:
        db = self.store.load_all()
        if not db:
            return None, None

        y = resample_mono(path, self.sr)
        ivals = split_by_vad(y, self.sr, self.vad_frame_ms, self.vad_aggr)
        if not ivals:
            return None, None

        embs = []
        for (st, en) in ivals:
            seg = y[st:en]
            if len(seg) / self.sr < 0.3:
                continue
            embs.append(self.ecapa.embed_signal(seg))
        if not embs:
            return None, None

        probe = np.vstack(embs).mean(axis=0).reshape(1, -1)
        names = list(db.keys())
        mats = np.vstack([db[n] for n in names])
        sims = cosine_similarity(probe, mats)[0]
        idx = int(np.argmax(sims))
        return names[idx], float(sims[idx])

    def diarize(self, path: str) -> List[Tuple[float, float, int]]:
        y = resample_mono(path, self.sr)

        ivals = split_by_vad(y, self.sr, self.vad_frame_ms, self.vad_aggr)
        if not ivals:
            dur = len(y) / self.sr
            return [(0.0, dur, 0)]

        win = int(self.diar_win * self.sr)
        hop = int(self.diar_hop * self.sr)
        X = []
        spans = []

        for (st, en) in ivals:
            seg = y[st:en]
            if len(seg) < max(1, win // 3):
                continue
            if win <= 0 or hop <= 0 or len(seg) <= win:
                emb = self.ecapa.embed_signal(seg)
                X.append(emb)
                spans.append((st / self.sr, en / self.sr))
            else:
                for s in range(0, len(seg) - win + 1, hop):
                    chunk = seg[s:s + win]
                    emb = self.ecapa.embed_signal(chunk)
                    X.append(emb)
                    spans.append(((st + s) / self.sr, (st + s + win) / self.sr))

        if not X:
            dur = len(y) / self.sr
            return [(0.0, dur, 0)]

        X = np.vstack(X)

        k = max(2, min(8, len(X) // 3))
        labels = AgglomerativeClustering(n_clusters=k).fit_predict(X)

        merged: List[Tuple[float, float, int]] = []
        cs, ce, cl = spans[0][0], spans[0][1], int(labels[0])
        for (st, en), lb in zip(spans[1:], labels[1:]):
            lb = int(lb)
            if lb == cl and st <= ce + 1e-3:
                ce = max(ce, en)
            else:
                merged.append((cs, ce, cl))
                cs, ce, cl = st, en, lb

        merged.append((cs, ce, cl))

        mapping = {}
        nxt = 0
        out = []
        for (s, e, l) in merged:
            if l not in mapping:
                mapping[l] = nxt
                nxt += 1
            out.append((float(s), float(e), mapping[l]))

        return out
