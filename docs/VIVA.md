# Viva questions

Use the file/function references to prepare your own answers. Evaluation figures below are from the synthetic-only run in [evaluation.md](evaluation.md); they are not real-world validation. References show the relevant implementation; design-rationale and privacy questions require your own reasoning.

1. **Why was Isolation Forest selected for this user-day anomaly problem?**

   File/function: [backend/app/ml/iforest.py](../backend/app/ml/iforest.py) — `IsolationForestModel.__init__`

   My answer:

2. **Why represent behaviour with these 18 user-day features?**

   File/function: [backend/app/features/build_features.py](../backend/app/features/build_features.py) — `compute_features`

   My answer:

3. **What does contamination="auto" control, and why is it used here?**

   File/function: [backend/app/ml/iforest.py](../backend/app/ml/iforest.py) — `IsolationForestModel.__init__`

   My answer:

4. **Why does the wrapper negate score_samples, and what does a higher result mean?**

   File/function: [backend/app/ml/iforest.py](../backend/app/ml/iforest.py) — `IsolationForestModel.score`

   My answer:

5. **How does the optional training cutoff prevent test-day leakage, and is it mandatory?**

   File/function: [backend/app/ml/train.py](../backend/app/ml/train.py) — `train`

   Evaluation: Synthetic split: 440 training and 200 test user-days.

   My answer:

6. **What happens if the training data already contains anomalous or insider activity?**

   File/function: [backend/app/ml/train.py](../backend/app/ml/train.py) — `train`

   My answer:

7. **How is a new user's first day handled when no rolling history exists?**

   File/function: [backend/app/features/build_features.py](../backend/app/features/build_features.py) — `compute_features`

   My answer:

8. **Why use the previous 14 active days for download statistics, and how is division by zero avoided?**

   File/function: [backend/app/features/build_features.py](../backend/app/features/build_features.py) — `compute_features`

   My answer:

9. **How are a previously unseen USB serial and a new device identified?**

   File/function: [backend/app/features/build_features.py](../backend/app/features/build_features.py) — `compute_features`

   My answer:

10. **Why are explanation rules separate from the anomaly model?**

   File/function: [backend/app/explain/rules.py](../backend/app/explain/rules.py) — `explain`

   Evaluation: Model-only, rules-only, and combined each had P@10 = 0.300 in the synthetic run.

   My answer:

11. **What does FIRST_USB mean, and what history does it inspect?**

   File/function: [backend/app/explain/rules.py](../backend/app/explain/rules.py) — `explain`

   My answer:

12. **What does calibration do to raw training scores and the 0–100 display score?**

   File/function: [backend/app/ml/calibration.py](../backend/app/ml/calibration.py) — `Calibration.from_training_scores / Calibration.risk_score`

   My answer:

13. **Why use training percentiles for risk levels instead of fixed raw anomaly scores?**

   File/function: [backend/app/ml/calibration.py](../backend/app/ml/calibration.py) — `Calibration.from_training_scores / Calibration.level`

   My answer:

14. **What changes when the Medium and High percentile thresholds move?**

   File/function: [backend/app/ml/calibration.py](../backend/app/ml/calibration.py) — `Calibration.from_training_scores / Calibration.level`

   Evaluation: At High 99.9, Medium 99 gave 20 alerts/1,000; Medium 95 gave 65/1,000.

   My answer:

15. **What does the negative-control result say about false positives?**

   File/function: [backend/app/ml/calibration.py](../backend/app/ml/calibration.py) — `Calibration.level`

   Evaluation: EMP004 was Medium at suggested defaults; anomaly score 0.666740.

   My answer:

16. **How should precision@10 and precision@50 be interpreted for this evaluation?**

   File/function: [backend/scripts/evaluate.py](../backend/scripts/evaluate.py) — `ranking_metrics`

   Evaluation: Synthetic model-only P@10 = 0.300; P@50 = 0.060.

   My answer:

17. **What does recall within the top 5% measure, and how many positives were available?**

   File/function: [backend/scripts/evaluate.py](../backend/scripts/evaluate.py) — `ranking_metrics`

   Evaluation: Recall = 1.000 in the top 10; there were 3 positive test user-days.

   My answer:

18. **Why compare model-only, rules-only and combined rankings without using the combination in the product?**

   File/function: [backend/app/ml/scoring.py](../backend/app/ml/scoring.py) — `score_features`

   Evaluation: All three synthetic rankings found 3 insiders in the top 10.

   My answer:

19. **What can the CERT dataset not establish about location novelty?**

   File/function: [backend/app/features/build_features.py](../backend/app/features/build_features.py) — `compute_features`

   My answer:

20. **What privacy risks arise from storing user-day features and event-linked reasons?**

   File/function: [backend/app/explain/rules.py](../backend/app/explain/rules.py) — `explain`

   My answer:

21. **Why use an application-owned PostgreSQL database, and how does the SQLite test path differ?**

   File/function: [backend/app/features/build_features.py](../backend/app/features/build_features.py) — `build_features`

   My answer:

22. **Why use JWT for analyst sessions, and what does the signing secret protect?**

   File/function: [backend/app/auth.py](../backend/app/auth.py) — `create_access_token / get_current_analyst`

   My answer:

23. **How does the model registry preserve the calibration and feature order for later scoring?**

   File/function: [backend/app/ml/registry.py](../backend/app/ml/registry.py) — `save / load_latest`

   My answer:

24. **How are analyst investigation decisions protected when scores are recalculated?**

   File/function: [backend/app/ml/scoring.py](../backend/app/ml/scoring.py) — `score_features`

   My answer:

25. **What limits generalization from the current evaluation to real insider threats?**

   File/function: [backend/scripts/evaluate.py](../backend/scripts/evaluate.py) — `evaluate`

   Evaluation: The run is synthetic only: 20 users, 200 test user-days and 3 labelled positives.

   My answer:

