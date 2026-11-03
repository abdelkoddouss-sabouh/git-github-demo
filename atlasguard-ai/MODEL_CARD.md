# Model card — AtlasGuard AI v0.1

**Purpose:** learning, portfolio demonstration and reproducible experimentation with imbalanced
tabular classification. **Not intended for:** blocking payments, investigating people or making
financial decisions about real customers.

## Training and evaluation

The simulator creates no personal data. A stochastic logistic rule generates the label from input
features, including one interaction. Consequently the benchmark partly rewards recovering the
simulator's own assumptions. It cannot establish external validity.

The late period increases amount, distance, attempts and device/international frequencies. The
underlying fraud rule remains fixed: this is covariate shift, not a demonstrated concept-drift test.
Examples have overlapping classes; perfect classification is neither expected nor required.

Chronological splitting uses distinct timestamp boundaries. The first 60% of unique timestamps
train models; 20% select by average precision and select a threshold by F1; the final 20% evaluate
the frozen selection. Scaling is fitted only on training. Boosting early stopping is disabled to
avoid silently introducing a random internal validation split.

The committed `examples/report.json` is one local experiment, not a guarantee. No confidence
intervals, cross-period backtests or real-data subgroup fairness analysis are implemented.
Fraud labels are available immediately in this simulator; real chargebacks can have long delays.

## Explanation and monitoring

Permutation importance is computed on validation using average precision and three shuffles.
It is a global model diagnostic, sensitive to correlated features, not a causal or per-case account.
PSI uses training quantile bins with smoothing; values are descriptive without universal cutoffs.

## Serving and operations

The API loads a local trusted joblib artifact, validates feature ranges and rejects extra inputs.
It returns a score and a threshold comparison. Calibration, authentication, rate limiting,
concurrency/load benchmarks, model registry, rollback and production monitoring are not supplied.
The API and dashboard bind to localhost in documented commands/configuration.

## Reproducibility

The report records seed, Python/sklearn versions, lake fingerprint, split ranges and actual metrics.
`examples/environment.txt` captures package versions from the executed environment. Different
versions can change outputs. Same seed and chunk size reproduce generation within an environment;
changing chunk size changes RNG draw ordering and therefore changes the dataset.
