#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-command launcher for Phase 1.
#   ./run.sh
# Uses the `tf` conda env if present, auto-detects GPU (falls back to CPU),
# installs anything missing, and writes results to ./outputs/.
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

# 1) Activate the `tf` conda env if available (otherwise use current python)
if command -v conda >/dev/null 2>&1; then
  source "$(conda info --base)/etc/profile.d/conda.sh" 2>/dev/null || true
  conda activate tf 2>/dev/null && echo "[run] using conda env: tf" \
    || echo "[run] 'tf' env not found — using current python"
fi

# 2) Ensure dependencies (idempotent; only installs if something is missing)
python - <<'PY' || { echo "[run] installing dependencies..."; pip install -q -r requirements.txt; }
import importlib.util as u, sys
need = ["torch","transformers","sentence_transformers","keybert","yake",
        "rapidfuzz","langdetect","openpyxl","sklearn","pandas","numpy"]
sys.exit(1 if [m for m in need if u.find_spec(m) is None] else 0)
PY

# 3) Pre-fetch models once (no-op if already cached; needs network only the
#    first time). Running fully offline afterwards is both safe and ~10x faster
#    for the enrichment stage (no per-call HF Hub network checks).
python -m pipeline.prefetch || true

# 4) Run the pipeline fully offline (auto-detects GPU; falls back to CPU)
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
python run_phase1.py
