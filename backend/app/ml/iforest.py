import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

class IsolationForestModel:
    def __init__(self):
        self.model = IsolationForest(n_estimators=200, random_state=42, contamination="auto")

    def fit(self, X: pd.DataFrame) -> "IsolationForestModel":
        self.model.fit(X)
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        return -self.model.score_samples(X)
