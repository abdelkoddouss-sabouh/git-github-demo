"""Chunked synthetic transactions. No real people, payments or banking claims."""
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES = ["amount", "hour", "distance_km", "attempts_1h", "account_age_days",
            "international", "new_device"]


def validate(frame):
    required = {"transaction_id", "timestamp", "is_fraud", *FEATURES}
    if required - set(frame):
        raise ValueError(f"Missing columns: {sorted(required - set(frame))}")
    if frame.empty or frame[list(required)].isna().any().any():
        raise ValueError("Empty dataset or missing values")
    if not frame.transaction_id.is_unique:
        raise ValueError("Duplicate transaction IDs")
    values = frame[FEATURES].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Features must be finite numbers")
    if (values < 0).any() or (frame.hour > 23).any():
        raise ValueError("Invalid feature range")
    for col in ["international", "new_device", "is_fraud"]:
        if not frame[col].isin([0, 1]).all():
            raise ValueError(f"{col} must be binary")
    times = pd.to_datetime(frame.timestamp, utc=True, errors="coerce")
    if times.isna().any() or not times.is_monotonic_increasing:
        raise ValueError("Timestamps must be valid and sorted")


def generate_lake(root, rows=100000, chunk_size=25000, seed=42):
    if rows < 1000 or chunk_size < 1:
        raise ValueError("Use at least 1000 rows and a positive chunk size")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    for start in range(0, rows, chunk_size):
        count = min(chunk_size, rows - start)
        ids = np.arange(start, start + count)
        time = pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(ids * 30, unit="s")
        # Late period changes feature distributions, not the hidden label rule.
        late = ids >= int(rows * .8)
        amount = np.round(rng.lognormal(3.7 + late * .2, 1.0, count), 2)
        distance = rng.exponential(25 + late * 15, count)
        attempts = rng.poisson(1.2 + late * .4, count)
        age = rng.integers(1, 1800, count)
        abroad = rng.binomial(1, .12 + late * .05, count)
        device = rng.binomial(1, .1 + late * .05, count)
        hour = time.hour.to_numpy()
        # Stochastic overlapping classes: features do not expose the target.
        logit = (-6.0 + .55 * np.log1p(amount / 50) + .6 * np.minimum(attempts, 8)
                 + .8 * abroad + 1.1 * device + .7 * (age < 45)
                 + .6 * (hour < 5) + .003 * np.minimum(distance, 400)
                 + .9 * abroad * device)
        probability = 1 / (1 + np.exp(-logit))
        frame = pd.DataFrame({"transaction_id": ids, "timestamp": time, "amount": amount,
                              "hour": hour, "distance_km": distance, "attempts_1h": attempts,
                              "account_age_days": age, "international": abroad,
                              "new_device": device, "is_fraud": rng.binomial(1, probability)})
        validate(frame)
        frame.to_parquet(root / f"part-{start // chunk_size:05d}.parquet", index=False)
    return root


def load_training_sample(root, max_rows=100000):
    """SQL scans Parquet; only a bounded, time-spread sample enters pandas/ML."""
    import duckdb
    paths = sorted(str(p) for p in Path(root).glob("part-*.parquet"))
    if not paths or max_rows < 1000:
        raise ValueError("Missing lake or sample size below 1000")
    with duckdb.connect() as con:
        con.execute("SET TimeZone='UTC'")
        relation = con.read_parquet(paths)
        relation.create_view("transactions")
        # Hash sampling is deterministic and independent of the target.
        sample = con.execute("SELECT * FROM transactions ORDER BY hash(transaction_id) LIMIT ?",
                             [int(max_rows)]).df().sort_values("timestamp").reset_index(drop=True)
        summary = con.execute("""SELECT count(*) AS rows, avg(is_fraud) AS fraud_rate,
            sum(amount) AS total_amount, min(timestamp) AS first_event,
            max(timestamp) AS last_event FROM transactions""").df().iloc[0].to_dict()
    validate(sample)
    return sample, {k: str(v) if hasattr(v, "isoformat") else v for k, v in summary.items()}
