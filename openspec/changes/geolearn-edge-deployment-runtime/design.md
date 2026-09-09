# Design: geolearn-edge-deployment-runtime

Export format: JSON bundle with base64-encoded weight arrays.

## classifier.json structure

```json
{
  "classes": ["0", "1", "2"],
  "n_features": 128,
  "n_samples": 450,
  "exported_at": "2026-09-09T12:00:00Z",
  "weights": "<base64-encoded float32 array>",
  "intercept": "<base64-encoded float32 array>"
}
```

## EdgeLoader inference

```python
def predict(self, X):
    W = np.frombuffer(base64.b64decode(self._weights), dtype=np.float32)
    b = np.frombuffer(base64.b64decode(self._intercept), dtype=np.float32)
    W = W.reshape((self.n_classes, self.n_features))
    logits = X @ W.T + b
    return np.argmax(logits, axis=1).tolist()
```

Pure numpy — no sklearn import required at runtime.
