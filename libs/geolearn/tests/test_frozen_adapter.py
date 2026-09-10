import numpy as np

from geolearn.cache import EmbeddingCache
from geolearn.classifier import OnlineClassifier
from geolearn.frozen_adapter import FrozenEmbeddingAdapter
from geolearn.models import PredictionResult
from geolearn.persistence import ClassifierStore


def test_frozen_embedding_adapter_knn_fallback(tmp_path):
    cache = EmbeddingCache(tmp_path)
    dim = 8

    # Labeled points: Class 1 near +1, Class 0 near -1
    e_pos1 = np.ones(dim, dtype=np.float32)
    e_pos2 = np.ones(dim, dtype=np.float32) * 0.9
    e_neg1 = -np.ones(dim, dtype=np.float32)
    e_neg2 = -np.ones(dim, dtype=np.float32) * 0.9

    cache.insert("p1", e_pos1, label=1)
    cache.insert("p2", e_pos2, label=1)
    cache.insert("n1", e_neg1, label=0)
    cache.insert("n2", e_neg2, label=0)

    adapter = FrozenEmbeddingAdapter(cache, k=3, n_training_samples=10)

    # Query point near positive cluster
    query_pos = np.ones(dim, dtype=np.float32) * 0.95
    res = adapter.predict(query_pos, key=("crop", "reg"))

    assert isinstance(res, PredictionResult)
    assert res.labels == [1]
    assert res.source == "nn_fallback"
    assert res.confidence[0] > 0.5
    assert not res.abstain

    # Query point near negative cluster
    query_neg = -np.ones(dim, dtype=np.float32) * 0.95
    res_neg = adapter.predict(query_neg, key=("crop", "reg"))
    assert res_neg.labels == [0]
    assert res_neg.source == "nn_fallback"


def test_frozen_embedding_adapter_classifier_delegation(tmp_path):
    cache = EmbeddingCache(tmp_path)
    dim = 4

    clf = OnlineClassifier()
    X = np.array([[1.0] * dim, [-1.0] * dim], dtype=np.float32)
    y = np.array([1, 0], dtype=np.int64)
    clf.fit(X, y)

    # When n_training_samples >= 30, it must delegate to classifier
    adapter = FrozenEmbeddingAdapter(
        cache,
        k=3,
        classifier=clf,
        n_training_samples=30,
    )

    query = np.array([[1.0] * dim], dtype=np.float32)
    res = adapter.predict(query, key=("crop", "reg"))

    assert res.source == "classifier"
    assert res.labels == [1]
    assert len(res.confidence) == 1


def test_frozen_embedding_adapter_register_label(tmp_path):
    cache = EmbeddingCache(tmp_path)
    dim = 4
    vec = np.zeros(dim, dtype=np.float32)
    cache.insert("asset_x", vec)

    adapter = FrozenEmbeddingAdapter(cache, k=1, n_training_samples=5)
    adapter.register_label("asset_x", 42)

    res = adapter.predict(vec)
    assert res.labels == [42]
    assert res.source == "nn_fallback"


def test_classifier_store_auto_selection(tmp_path):
    store = ClassifierStore(tmp_path)
    key = ("wheat", "fars")
    dim = 4

    # Populate cache with labeled samples
    v_pos = np.ones(dim, dtype=np.float32)
    v_neg = -np.ones(dim, dtype=np.float32)
    store.cache.insert("a1", v_pos, label=1)
    store.cache.insert("a2", v_neg, label=0)

    clf = OnlineClassifier()
    clf.fit([v_pos, v_neg], [1, 0])

    # Scenario A: n_samples < 30 -> NN fallback
    store.save_classifier(key, clf, n_samples=15)
    res_low = store.predict(v_pos, key=key)
    assert res_low.source == "nn_fallback"
    assert res_low.labels == [1]

    # Scenario B: n_samples >= 30 -> Classifier
    store.save_classifier(key, clf, n_samples=35)
    res_high = store.predict(v_pos, key=key)
    assert res_high.source == "classifier"
    assert res_high.labels == [1]
