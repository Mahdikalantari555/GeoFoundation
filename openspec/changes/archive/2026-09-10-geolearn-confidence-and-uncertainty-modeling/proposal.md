## Why

Prediction confidence is only as good as the calibration behind it. Raw
SGDClassifier probabilities are uncalibrated (they reflect distance to
decision boundary, not true correctness probability). Without calibration,
the abstention signal is unreliable — the agent either abstains too often
(false negative) or not often enough (false positive). This change adds
proper confidence calibration and uncertainty estimation.

## What Changes

1. Add `CalibrationCurve` class: maintains a running histogram of
   (predicted_probability, actual_correct) pairs, fit with isotonic
   regression (`sklearn.isotonic.IsotonicRegression`) on a validation
   window. Returns calibrated probabilities on demand.
2. Add `prediction_entropy(embedding, proba)` helper: computes Shannon
   entropy of the prediction distribution as an additional uncertainty
   signal.
3. Combine calibrated probability + entropy into a unified `confidence_score`
   returned in `PredictionResult`.
4. When entropy > threshold (default 0.8 bits), force abstain regardless
   of calibrated probability.

## Capabilities

### New Capabilities
- `geolearn-confidence-and-uncertainty-modeling`: calibrated probabilities + entropy.

## Impact

- Calibration uses a held-out validation window (default last 100 samples);
  no extra data collection needed.
- Isotonic regression is included in scikit-learn — no new dependencies.
- Entropy computation is pure numpy.
