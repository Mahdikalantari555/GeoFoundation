#!/usr/bin/env python3
"""CI gate: pip install geomemory (base) must not pull torch/txtai/sentence-transformers."""
import importlib.metadata, sys

dist = importlib.metadata.distribution("geomemory")
requires = list(dist.requires or [])
bad = []
for r in requires:
    low = r.lower()
    for token in ("torch", "txtai", "sentence-transformers", "safetensors", "accelerate"):
        if token in low:
            # Allow if it's under an extra (e.g. extra == "vision" or extra == "llamacpp")
            if 'extra ==' in low and ('vision' in low or 'llamacpp' in low):
                continue
            bad.append((token, r))

if bad:
    print("FAIL: banned token in Requires-Dist (outside opt-in extra):")
    for tok, r in bad:
        print(f"  {tok}: {r}")
    sys.exit(1)
print("OK: no torch/txtai/sentence-transformers in base Requires-Dist")
# Base pip freeze should not have torch/txtai unless vision installed
import subprocess
try:
    out = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    low = out.lower()
    # Only fail if torch installed but we didn't request vision — check if geomemory[vision] is installed? For now warn
    if "torch==" in low or "txtai==" in low:
        print("NOTE: torch/txtai found in pip freeze (may be via vision/opt-in or unrelated env dep)")
        # Don't fail, just note — base gate is Requires-Dist; vision opt-in is allowed
    else:
        print("OK: pip freeze clean for base (no torch/txtai)")
except Exception as e:
    print(f"warning: pip freeze check skipped: {e}")
