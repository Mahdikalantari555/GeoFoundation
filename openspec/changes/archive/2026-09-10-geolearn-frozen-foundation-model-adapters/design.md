# Design: geolearn-frozen-foundation-model-adapters

NN fallback bridges the gap between "no training data" and "classifier ready".

## Threshold logic

```python
MIN_SAMPLES_FOR_CLASSIFIER = 30

def predict(self, embedding, key, user_id=None):
    clf = self.get_classifier(key)
    if clf.n_samples_ >= MIN_SAMPLES_FOR_CLASSIFIER:
        return clf.predict_with_source(embedding, key, source="classifier")
    else:
        adapter = FrozenEmbeddingAdapter(self.cache, k=5)
        return adapter.predict(embedding, key)
```

## Neighbor voting

Weighted by inverse distance: closer neighbors vote more heavily.
Confidence = sum of weights for winning class / total weight.

## No embedding regeneration

The adapter only reads from EmbeddingCache. It never calls OLMoEarth directly —
embedding generation remains the caller's responsibility (handled by GeoAgent's
ingestion pipeline).
