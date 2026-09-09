# Design: geolearn-region-specific-adaptation

Hierarchical keys: `crop.region` and optionally `crop.region.subregion`.

## Weight transfer

When a sub-region classifier is first accessed:
1. Find parent classifier (crop.region).
2. If parent exists and has trained parameters, copy coef_ and intercept_.
3. Set n_samples_ = 0 for sub-region (fresh gradient accumulation).
4. First partial_fit() on sub-region adds gradient on top of transferred weights.

## Schema extension

```sql
ALTER TABLE classifier_state ADD COLUMN sub_region TEXT NULL;
-- Existing rows have NULL; new sub-region entries get the value.
```

Migration is idempotent (ALTER TABLE ADD COLUMN is safe to run repeatedly).
