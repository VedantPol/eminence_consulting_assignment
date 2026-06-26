"""
One-time model prefetch. Downloads the local models into the HuggingFace cache
if they are not already present (a no-op on subsequent runs). After this, the
pipeline can run fully offline (HF_HUB_OFFLINE=1) — which is also much faster
because it skips per-call network checks.

Usage:  python -m pipeline.prefetch
"""
from __future__ import annotations
from pipeline import config as C

MODELS = [
    C.MODEL_SENTIMENT, C.MODEL_SENTIMENT_SOCIAL,
    C.MODEL_ZEROSHOT, C.MODEL_EMOTION, C.MODEL_EMBED,
]
_IGNORE = ["*.onnx", "*.msgpack", "*.h5", "*tf_model*", "rust_model*", "*openvino*"]


def main() -> None:
    from huggingface_hub import snapshot_download
    for m in MODELS:
        try:
            snapshot_download(m, ignore_patterns=_IGNORE)
            print(f"[prefetch] ready: {m}")
        except Exception as e:  # offline + already cached, or transient network
            print(f"[prefetch] skip {m}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
