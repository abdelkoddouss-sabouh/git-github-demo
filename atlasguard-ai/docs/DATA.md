# Data contract

All events are synthetic and timestamped 30 seconds apart from 2026-01-01 UTC.
No name, account number, card identifier or sensitive attribute is generated.

| Column | Type | Meaning | Model input |
|---|---|---|---|
| transaction_id | integer | Unique synthetic event ID | No |
| timestamp | UTC timestamp | Event time, sorted | No |
| amount | nonnegative float | Amount in unspecified demo currency units | Yes |
| hour | integer 0–23 | UTC hour | Yes |
| distance_km | nonnegative float | Simulated distance from usual location | Yes |
| attempts_1h | nonnegative integer | Simulated recent attempt count | Yes |
| account_age_days | nonnegative integer | Simulated account age | Yes |
| international | 0 or 1 | Simulated cross-border indicator | Yes |
| new_device | 0 or 1 | Simulated device novelty | Yes |
| is_fraud | 0 or 1 | Stochastic outcome known offline | No, target only |

The attempt count is a generated feature, not a window computed from a real event stream.
The simulator's 80% shift boundary is based on generated row position; the hashed training sample
approximates the same proportions but need not align with that boundary exactly.

Validation checks missing values, uniqueness within each batch/sample, binary labels, finite
nonnegative inputs and sorted timestamps. It does not currently ingest arbitrary third-party data.
An integration with real transactions needs licensing checks, schema mapping, label-delay handling,
privacy controls, realistic temporal validation and additional data-quality constraints.
