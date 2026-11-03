"""python -m atlasguard.pipeline --rows 100000 --output artifacts"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import joblib
import pandas as pd
import sklearn
from sklearn.inspection import permutation_importance
from sklearn.metrics import precision_recall_curve
from .data import FEATURES, generate_lake, load_training_sample
from .model import candidates, chronological_split, choose_threshold, metrics, drift


def run(output, rows=100000, max_train_rows=100000, seed=42):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    lake = generate_lake(output / "lake", rows=rows, seed=seed)
    frame, summary = load_training_sample(lake, max_train_rows)
    train, valid, test = chronological_split(frame)
    fitted, comparisons, thresholds = {}, {}, {}
    for name, estimator in candidates(seed).items():
        estimator.fit(train[FEATURES], train.is_fraud)
        scores = estimator.predict_proba(valid[FEATURES])[:, 1]
        threshold = choose_threshold(valid.is_fraud, scores)
        fitted[name], thresholds[name] = estimator, threshold
        comparisons[name] = metrics(valid.is_fraud, scores, threshold)
    winner = max(comparisons, key=lambda n: comparisons[n]["average_precision"])
    model, threshold = fitted[winner], thresholds[winner]
    scores = model.predict_proba(test[FEATURES])[:, 1]
    results = metrics(test.is_fraud, scores, threshold)
    importance = permutation_importance(model, valid[FEATURES], valid.is_fraud,
                                        scoring="average_precision", n_repeats=3, random_state=seed)
    scored = test.copy()
    scored["risk_score"] = scores
    scored.to_parquet(output / "test_scores.parquet", index=False)
    bundle = {"model": model, "threshold": threshold, "features": FEATURES, "source": "synthetic"}
    joblib.dump(bundle, output / "model.joblib")
    fingerprint = hashlib.sha256()
    for path in sorted(lake.glob("*.parquet")):
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                fingerprint.update(chunk)
    report = {"project": "AtlasGuard AI", "source": "synthetic", "seed": seed,
              "lake": summary, "sample_rows": len(frame), "lake_sha256": fingerprint.hexdigest(),
              "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__},
              "split": {name: {"rows": len(part), "fraud_rate": float(part.is_fraud.mean()),
                                "first": str(part.timestamp.min()), "last": str(part.timestamp.max())}
                        for name, part in zip(["train", "validation", "test"], [train, valid, test])},
              "selection_metric": "validation average precision", "validation": comparisons,
              "winner": winner, "threshold": threshold, "threshold_selection": "validation F1",
              "test": results, "drift_psi": drift(train, test, FEATURES),
              "permutation_importance_validation": dict(zip(FEATURES, importance.importances_mean.tolist())),
              "limitations": ["Synthetic data only; not validated on real fraud",
                               "Batch processing, not a live payment stream",
                               "ML sample capped in memory; lake scans use DuckDB",
                               "Threshold optimizes validation F1, not real monetary cost"]}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Export an exact precision-recall curve for the held-out test.
    p, r, _ = precision_recall_curve(test.is_fraud, scores)
    pd.DataFrame({"precision": p, "recall": r}).to_csv(output / "pr_curve.csv", index=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--max-train-rows", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()
    if args.rows < 1000 or args.max_train_rows < 1000:
        parser.error("--rows and --max-train-rows must be at least 1000")
    if Path(args.output).exists():
        parser.error("Output already exists; choose another --output to preserve previous runs")
    report = run(args.output, args.rows, args.max_train_rows, args.seed)
    print(json.dumps({"winner": report["winner"], "test": report["test"]}, indent=2))


if __name__ == "__main__":
    main()
