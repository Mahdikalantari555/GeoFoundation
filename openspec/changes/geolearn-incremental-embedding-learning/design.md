# Design: geolearn-incremental-embedding-learning

Association map is a lightweight overlay on top of the classifier.

## Score update formula

On new sample (hash H, label L):
```
scores[(H, L)] += 1.0
for (h, l) in scores:
    dt = (now - last_update_time[h]).days
    scores[(h, l)] *= exp(-dt / half_life_days)
# Prune
scores = {k: v for k, v in scores.items() if v >= 0.01}
```

## Hash computation

SHA-256 of numpy bytes.tobytes() of the embedding vector (not the cached array,
to avoid storing full vectors in the association map).

## Blend

```python
blended = 0.5 * classifier_proba + 0.5 * association_vote
```

association_vote for class c = sum of scores for (hash, c) / total scores for hash.
If no association entries exist for the hash, association_vote = uniform (1/n_classes).
