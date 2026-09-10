# geolearn-confidence-and-uncertainty-modeling — Specification (v0.2)

Adds calibration curves and entropy-based uncertainty estimation to improve
abstention reliability.

## Requirements

### Requirement: CalibrationCurve
`CalibrationCurve(window_size=100)` SHALL maintain a rolling buffer of
`(predicted_proba, is_correct)` pairs and fit an isotonic regression
(`sklearn.isotonic.IsotonicRegression`) on demand. `calibrate(proba) -> float`
returns the calibrated probability.

#### Scenario: Calibration improves low-confidence signal
- **WHEN** raw predict_proba gives 0.55 for a actually-correct prediction
- **THEN** calibrated probability is closer to 1.0 (upward adjustment)

#### Scenario: Insufficient data for calibration
- **WHEN** fewer than 10 validation samples exist
- **THEN** `calibrate()` returns the raw proba unchanged (no calibration applied)

### Requirement: Prediction entropy
`prediction_entropy(proba_array) -> float` SHALL compute
`-sum(p * log(p))` for non-zero probabilities, returning bits.

#### Scenario: Entropy bounds
- **WHEN** proba = [1.0, 0.0, 0.0] → entropy = 0.0
- **WHEN** proba = [0.33, 0.33, 0.34] → entropy ≈ 1.09 bits

### Requirement: Combined confidence score
`ConfidenceModel.compute_final_confidence(calibrated_proba, entropy) -> float`
SHALL blend the two signals:
```
final = 0.7 * calibrated_proba + 0.3 * (1.0 - min(entropy / log(2), 1.0))
```
Higher entropy reduces confidence even when calibrated probability is high.

### Requirement: Entropy-based abstention
When `entropy > entropy_threshold` (default 0.8 bits), the prediction is
marked as abstain regardless of calibrated probability.

#### Scenario: High entropy forces abstain
- **WHEN** proba = [0.4, 0.35, 0.25] (entropy ≈ 1.08 bits)
- **THEN** abstain=True even though max proba > 0.6

## Non-goals

- Temperature scaling
- Monte Carlo dropout
- Bayesian posterior estimation
