from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class Calibration:
    lo: float
    med_cut: float
    high_cut: float
    hi: float

    @classmethod
    def from_training_scores(cls, scores, medium_pct=97, high_pct=99.5):
        values = np.asarray(scores, dtype=float)
        if values.ndim != 1 or not values.size or not np.isfinite(values).all():
            raise ValueError("Training scores must be a nonempty finite one-dimensional array")
        if not 50 <= medium_pct <= high_pct <= 100:
            raise ValueError("Percentiles must satisfy 50 <= medium <= high <= 100")
        lo = float(np.median(values))
        med = float(np.percentile(values, medium_pct))
        high = float(np.percentile(values, high_pct))
        return cls(lo, med, high, max(float(np.max(values)), high + (high - med)))

    def risk_score(self, score):
        return round(float(np.interp(score, [self.lo, self.med_cut, self.high_cut, self.hi], [0, 40, 70, 100])))

    def level(self, score):
        if score >= self.high_cut:
            return "High"
        if score >= self.med_cut:
            return "Medium"
        return "Low"
