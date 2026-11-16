"""Novelty-mode Local Outlier Factor implementing the anomaly model interface."""
import numpy as np
import pandas as pd
from sklearn.neighbors import LocalOutlierFactor


class LocalOutlierFactorModel:
    def __init__(self):
        self.model = LocalOutlierFactor(novelty=True)

    def fit(self, X: pd.DataFrame) -> "LocalOutlierFactorModel":
        if len(X) < 2:
            raise ValueError("LOF requires at least two training rows")
        self.model.fit(X)
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        return -self.model.score_samples(X)
