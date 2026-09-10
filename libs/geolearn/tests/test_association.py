import numpy as np
import pytest

from geolearn.association import AssociationMap
from geolearn.classifier import OnlineClassifier


def test_association_map_update_and_reinforce():
    assoc = AssociationMap(half_life_days=90)
    emb = [0.1, 0.2, 0.3]

    # First observation
    s1 = assoc.update(emb, label=1)
    assert s1 == 1.0

    scores = assoc.scores_for(emb)
    assert scores == {1: 1.0}

    # Reinforce existing association
    s2 = assoc.update(emb, label=1)
    assert s2 == 2.0
    assert assoc.scores_for(emb) == {1: 2.0}

    # Different label on same embedding
    assoc.update(emb, label=0)
    scores = assoc.scores_for(emb)
    assert scores == {0: 1.0, 1: 2.0}


def test_association_map_decay_halving():
    assoc = AssociationMap(half_life_days=90)
    emb = [1.0, 0.0]

    for _ in range(6):
        assoc.update(emb, label=1)
    assert assoc.scores_for(emb)[1] == 6.0

    # 90 days pass: scores must be exactly halved
    assoc.decay(dt_days=90.0)
    assert pytest.approx(assoc.scores_for(emb)[1], rel=1e-4) == 3.0

    # Another 90 days
    assoc.decay(dt_days=90.0)
    assert pytest.approx(assoc.scores_for(emb)[1], rel=1e-4) == 1.5


def test_association_map_prunes_below_001():
    assoc = AssociationMap(half_life_days=10)
    emb = [0.5, 0.5]
    assoc.update(emb, label=2)

    # Decay enough that 1.0 * (0.5 ** (dt / 10)) < 0.01 (e.g. dt=70 gives ~0.0078)
    assoc.decay(dt_days=70.0)
    assert assoc.scores_for(emb) == {}


def test_association_map_blend():
    assoc = AssociationMap(half_life_days=90)
    emb = [1.0, 2.0]

    # 1. Map has no entries: proba returned unchanged
    raw_proba = np.array([0.8, 0.2], dtype=np.float64)
    blended = assoc.blend(raw_proba, emb, classes=[0, 1])
    assert np.allclose(blended, raw_proba)

    # 2. Add associations pointing to class 1
    assoc.update(emb, label=1)
    # raw_proba = [0.8, 0.2]
    # assoc_dist = [0.0, 1.0]
    # blended = 0.5 * [0.8, 0.2] + 0.5 * [0.0, 1.0] = [0.4, 0.6]
    blended2 = assoc.blend(raw_proba, emb, classes=[0, 1])
    assert np.allclose(blended2, [0.4, 0.6])


def test_online_classifier_blend_integration():
    assoc = AssociationMap(half_life_days=90)
    clf = OnlineClassifier(association_map=assoc)

    X = np.array([[1.0, 1.0], [-1.0, -1.0]])
    y = np.array([1, 0])
    clf.fit(X, y)

    # Test point initially favors class 1 slightly
    test_x = np.array([[0.1, 0.1]])
    initial_preds = clf.predict(test_x)
    initial_proba = clf.predict_proba(test_x)[0]

    # Populate association map with strong association for class 0
    for _ in range(10):
        assoc.update(test_x[0], label=0)

    blended_proba = clf.predict_proba(test_x)[0]
    blended_preds = clf.predict(test_x)

    # Class 0 probability should be significantly higher after blend
    assert blended_proba[0] > initial_proba[0]
    assert blended_preds[0] == 0
