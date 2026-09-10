import numpy as np
import pytest
from geolearn.cache import EmbeddingCache

def test_cache_insert_and_lookup(tmp_path):
    cache = EmbeddingCache(tmp_path)
    vec = np.random.randn(128).astype(np.float32)
    cache.insert("asset_1", vec)

    ret = cache.lookup("asset_1")
    assert ret is not None
    assert ret.dtype == np.float32
    assert np.allclose(ret, vec)

    # Miss
    assert cache.lookup("nonexistent") is None

def test_cache_nn_lookup(tmp_path):
    cache = EmbeddingCache(tmp_path)
    base = np.zeros(16, dtype=np.float32)
    v1 = base + 0.1
    v2 = base + 0.2
    v3 = base + 0.3
    v4 = base + 1.0

    cache.insert("a1", v1)
    cache.insert("a2", v2)
    cache.insert("a3", v3)
    cache.insert("a4", v4)

    nn = cache.nn_lookup(base, k=3)
    assert len(nn) == 3
    assert [item[0] for item in nn] == ["a1", "a2", "a3"]
    assert nn[0][1] < nn[1][1] < nn[2][1]
