# ONNX Spike Report: OLMoEarth Nano v1.2 Export

**Date**: 2025-07-18  
**Status**: In progress  
**Change**: `olmoearth-production-and-onnx-spike` Track B

## Goal

Determine whether exporting the OLMoEarth v1.2 Nano PyTorch checkpoint to ONNX
produces acceptable quality, latency, and model size vs. the native torch path.

## Acceptance Criteria (from spec)

| Metric | Threshold |
|---|---|
| Mean cosine distance (torch vs ONNX) | ≤ 0.02 |
| ONNX model file size | Documented vs. torch .pth |
| Per-image embedding latency (mean over 50 runs) | Documented ms |

## Scripts

- `scripts/export_olmoearth_onnx.py` — exports `.pth` → `.onnx`
- `scripts/benchmark_olmoearth_onnx.py` — compares quality + latency

Both scripts exit with code 1 and a clear message when `torch`, `onnx`, or
`onnxruntime` are unavailable so CI can skip the spike gracefully.

## Results

_Pending experiment run._

## Risks / Notes

- OLMoEarth's encoder may use ops not yet supported by ONNX export (custom attention patterns). If export fails, Track A proceeds with torch-only and Change 3 designs for one vision space.
- This spike tests FP16 only; INT8 quantization is deferred.
- `apps/dashboard/` does not exist in this repo — the web UI lives at
  `apps/web/` (React Vite). A dedicated image-search page is tracked as Task A3
  in the production spec.
