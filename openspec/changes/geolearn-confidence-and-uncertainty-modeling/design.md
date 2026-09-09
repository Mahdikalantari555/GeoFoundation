# Design: geolearn-confidence-and-uncertainty-modeling

Calibration improves raw probability reliability; entropy catches ambiguity.

## CalibrationCurve internals

Buffer: deque of (proba, is_correct) tuples, maxlen=window_size.
On calibrate(proba):
- If len(buffer) < 10: return proba (insufficient data)
- Fit IsotonicRegression on buffer
- Return clipped transformed value [0, 1]

## Entropy formula

H(p) = -sum(p_i * log2(p_i)) for p_i > 0

Bounded: max entropy for K classes = log2(K). Normalized: H / log2(K) ∈ [0, 1].

## Final confidence blend

final = 0.7 * calibrated_proba + 0.3 * (1.0 - normalized_entropy)

When entropy is high (ambiguous), final drops even if calibrated proba is moderate.
When entropy is zero (certain), final ≈ calibrated_proba.
