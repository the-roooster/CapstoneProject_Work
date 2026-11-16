from typing import Protocol
import numpy as np
import pandas as pd

class AnomalyModel(Protocol):
    def fit(self, X: pd.DataFrame) -> "AnomalyModel": ...
    def score(self, X: pd.DataFrame) -> np.ndarray:
        """Higher scores indicate greater anomaly."""
        ...
