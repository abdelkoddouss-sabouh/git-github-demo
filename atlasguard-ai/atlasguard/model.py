"""Train-only transforms, validation-only selection, untouched chronological test."""
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (average_precision_score, roc_auc_score, precision_recall_curve,
                             confusion_matrix, precision_score, recall_score, f1_score)


def chronological_split(frame):
    # Never split equal timestamps across boundaries (important for real-data extensions).
    times = frame.timestamp.drop_duplicates().sort_values().to_numpy()
    if len(times) < 10:
        raise ValueError("At least 10 distinct timestamps required")
    a, b = times[int(len(times) * .6)], times[int(len(times) * .8)]
    splits = (frame[frame.timestamp < a], frame[(frame.timestamp >= a) & (frame.timestamp < b)],
              frame[frame.timestamp >= b])
    if any(s.is_fraud.nunique() != 2 for s in splits):
        raise ValueError("Every chronological split must contain both classes; generate more rows")
    return splits


def choose_threshold(y, scores):
    precision, recall, thresholds = precision_recall_curve(y, scores)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[np.argmax(f1)])


def metrics(y, scores, threshold):
    prediction = np.asarray(scores) >= threshold
    tn, fp, fn, tp = confusion_matrix(y, prediction, labels=[0, 1]).ravel()
    return {"average_precision": float(average_precision_score(y, scores)),
            "roc_auc": float(roc_auc_score(y, scores)),
            "precision": float(precision_score(y, prediction, zero_division=0)),
            "recall": float(recall_score(y, prediction, zero_division=0)),
            "f1": float(f1_score(y, prediction, zero_division=0)),
            "alerts": int(prediction.sum()), "tn": int(tn), "fp": int(fp),
            "fn": int(fn), "tp": int(tp)}


def candidates(seed):
    return {"baseline": DummyClassifier(strategy="prior"),
            "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)),
            "gradient_boosting": HistGradientBoostingClassifier(
                max_iter=120, max_leaf_nodes=15, l2_regularization=3,
                early_stopping=False, random_state=seed)}


def drift(train, test, features):
    """Population stability index using train-only bins; descriptive, not a verdict."""
    result = {}
    for col in features:
        bins = np.unique(np.quantile(train[col], np.linspace(0, 1, 11)))
        if len(bins) < 3:
            bins = np.array([-np.inf, .5, np.inf])
        else:
            bins[0], bins[-1] = -np.inf, np.inf
        a = np.histogram(train[col], bins)[0].astype(float) + .5
        b = np.histogram(test[col], bins)[0].astype(float) + .5
        a, b = a / a.sum(), b / b.sum()
        result[col] = float(np.sum((b - a) * np.log(b / a)))
    return result
