"""
Hardware auto-detection so the pipeline runs fast on a GPU box and still works
unchanged on any laptop.

Priority: CUDA GPU  ->  Apple MPS  ->  CPU (all cores).
On GPU we use fp16 + large batches; on CPU we pin every core and use small
batches. `force_cpu=True` gives a guaranteed-portable fallback path.
"""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class DeviceConfig:
    kind: str            # "cuda" | "mps" | "cpu"
    name: str            # human-readable
    pipe_device: object  # value for transformers pipeline(device=...)
    st_device: str       # value for SentenceTransformer(device=...)
    dtype: object        # torch dtype for model weights
    zs_batch: int        # zero-shot batch size
    cls_batch: int       # sentiment/emotion batch size
    embed_batch: int     # embedding batch size
    threads: int         # CPU threads used


def detect(force_cpu: bool = False) -> DeviceConfig:
    import torch

    n_cores = os.cpu_count() or 4
    # Always let intra-op parallelism use every core (matters for CPU + tokenizers)
    try:
        torch.set_num_threads(n_cores)
    except Exception:
        pass

    if not force_cpu and torch.cuda.is_available():
        return DeviceConfig(
            kind="cuda",
            name=torch.cuda.get_device_name(0),
            pipe_device=0,
            st_device="cuda",
            dtype=torch.float16,
            zs_batch=32, cls_batch=64, embed_batch=128,
            threads=n_cores,
        )

    mps = getattr(getattr(__import__("torch").backends, "mps", None), "is_available", lambda: False)()
    if not force_cpu and mps:
        return DeviceConfig(
            kind="mps", name="Apple MPS", pipe_device="mps", st_device="mps",
            dtype=torch.float32, zs_batch=16, cls_batch=32, embed_batch=64,
            threads=n_cores,
        )

    return DeviceConfig(
        kind="cpu", name=f"CPU ({n_cores} cores)", pipe_device=-1, st_device="cpu",
        dtype=torch.float32, zs_batch=8, cls_batch=16, embed_batch=32,
        threads=n_cores,
    )
