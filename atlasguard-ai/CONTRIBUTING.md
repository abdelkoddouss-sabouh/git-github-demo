# Contributing

Install with `python -m pip install -e ".[dev]"`, then run `python -m pytest -q`.
Keep labels, identifiers and future-derived information out of model inputs.
Every claimed result must point to the command, data source and actual artifact that produced it.

Useful follow-ups:

- Add a licensed real dataset adapter and its data card.
- Implement delayed-label temporal backtesting.
- Compare sampling strategies and measure memory/time on larger lakes.
- Add calibrated scores using a separate calibration period.
- Implement causal event-time rolling features and test for future leakage.

Avoid adding infrastructure solely for a technology badge. Explain the problem a dependency solves.
