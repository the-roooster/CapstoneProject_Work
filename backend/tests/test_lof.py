import numpy as np
import pandas as pd
import pytest

from app.ml.lof import LocalOutlierFactorModel


def test_novelty_score_orders_a_distant_point_above_normal():
    train = pd.DataFrame({"x": np.linspace(-1, 1, 50), "y": np.zeros(50)})
    model = LocalOutlierFactorModel().fit(train)
    points = pd.DataFrame({"x": [0.0, 20.0], "y": [0.0, 20.0]})
    scores = model.score(points)
    assert scores.shape == (2,)
    assert scores[1] > scores[0]


def test_lof_rejects_insufficient_training_rows():
    with pytest.raises(ValueError, match="at least two"):
        LocalOutlierFactorModel().fit(pd.DataFrame({"x": [1.0]}))
