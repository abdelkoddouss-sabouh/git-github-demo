import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from atlasguard.data import FEATURES, generate_lake, load_training_sample, validate
from atlasguard.model import chronological_split, choose_threshold, metrics
from atlasguard.pipeline import run
from atlasguard.api import app


def test_seeded_chunked_lake_and_sql(tmp_path):
    a = generate_lake(tmp_path / "a", rows=3000, chunk_size=700)
    b = generate_lake(tmp_path / "b", rows=3000, chunk_size=700)
    x, totals = load_training_sample(a, 1500)
    y, _ = load_training_sample(b, 1500)
    pd.testing.assert_frame_equal(x, y)
    assert len(list(a.glob("*.parquet"))) == 5
    assert totals["rows"] == 3000 and len(x) == 1500
    train, valid, test = chronological_split(x)
    assert train.timestamp.max() < valid.timestamp.min() < test.timestamp.min()
    assert set(FEATURES).isdisjoint({"timestamp", "transaction_id", "is_fraud"})


def test_validation_rejects_corruption(tmp_path):
    frame, _ = load_training_sample(generate_lake(tmp_path / "lake", rows=1000))
    frame.loc[0, "amount"] = np.inf
    with pytest.raises(ValueError, match="finite"):
        validate(frame)


def test_threshold_and_confusion_counts():
    y, p = [0, 0, 1, 1], [.1, .2, .7, .9]
    t = choose_threshold(y, p)
    result = metrics(y, p, t)
    assert result["tp"] == 2 and result["fp"] == 0
    assert result["f1"] == 1


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    path = tmp_path_factory.mktemp("experiment") / "run"
    report = run(path, rows=6000, max_train_rows=4000)
    return path, report


def test_pipeline_artifacts_and_reproducible_contract(trained):
    path, report = trained
    assert report["source"] == "synthetic"
    assert sum(x["rows"] for x in report["split"].values()) == 4000
    assert set(report["validation"]) == {"baseline", "logistic", "gradient_boosting"}
    assert report["winner"] == max(report["validation"], key=lambda n: report["validation"][n]["average_precision"])
    assert json.loads((path / "report.json").read_text())["test"] == report["test"]
    m = report["test"]
    assert sum(m[x] for x in ["tn", "fp", "fn", "tp"]) == report["split"]["test"]["rows"]
    with pytest.raises(FileExistsError):
        run(path, rows=1000)


def test_api_matches_batch_model_and_rejects_bad_input(trained, monkeypatch):
    path, _ = trained
    monkeypatch.setenv("ATLAS_ARTIFACTS", str(path))
    test = pd.read_parquet(path / "test_scores.parquet")
    item = test.iloc[0]
    payload = {x: float(item[x]) if x in ["amount", "distance_km"] else int(item[x]) for x in FEATURES}
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ready"
        response = client.post("/predict", json=payload)
        assert response.status_code == 200
        assert response.json()["risk_score"] == pytest.approx(item.risk_score)
        assert client.post("/predict", json={**payload, "hour": 24}).status_code == 422
        assert client.post("/predict", json={**payload, "is_fraud": 1}).status_code == 422


def test_missing_model_returns_503(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_ARTIFACTS", str(tmp_path))
    with TestClient(app) as client:
        response = client.post("/predict", json={"amount": 20, "hour": 12, "distance_km": 2,
            "attempts_1h": 1, "account_age_days": 100, "international": 0, "new_device": 0})
        assert response.status_code == 503


def test_dashboard_renders_and_threshold_changes(trained, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    path, _ = trained
    monkeypatch.setenv("ATLAS_ARTIFACTS", str(path))
    dashboard = Path(__file__).resolve().parents[1] / "dashboard.py"
    view = AppTest.from_file(str(dashboard)).run(timeout=30)
    assert not view.exception
    assert view.title[0].value == "Signals become decisions."
    view.slider[0].set_value(1.0).run(timeout=30)
    assert not view.exception
    assert next(m for m in view.metric if m.label == "Alerts").value == "0"
