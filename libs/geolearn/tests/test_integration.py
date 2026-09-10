import numpy as np
from geolearn import OnlineClassifier, EmbeddingCache, PredictionResult, ConfidenceModel, ClassifierStore

def test_full_pipeline_integration(tmp_path):
    cache = EmbeddingCache(tmp_path)
    store = ClassifierStore(tmp_path)
    conf_model = ConfidenceModel(threshold=0.6)

    # 1. Populate cache with embeddings
    dim = 8
    e1 = np.ones(dim, dtype=np.float32)
    e2 = -np.ones(dim, dtype=np.float32)
    cache.insert("asset_wheat_1", e1)
    cache.insert("asset_wheat_2", e2)

    # 2. Train classifier
    clf = OnlineClassifier()
    clf.fit([e1, e2], [1, 0])
    store.save_classifier(("wheat", "khuzestan"), clf, n_samples=2)

    # 3. Predict new asset
    query = np.ones(dim, dtype=np.float32) * 0.95
    res = store.predict_for_key(query, key=("wheat", "khuzestan"), confidence_model=conf_model)

    assert isinstance(res, PredictionResult)
    assert res.labels == [1]
    assert res.confidence[0] >= 0.6
    assert res.abstain is False
    assert res.key == ("wheat", "khuzestan")
    assert res.n_samples == 1
    assert len(res.model_version) == 64
