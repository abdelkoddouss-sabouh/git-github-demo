"""Export lightweight, measured artifacts for GitHub; no model binaries or transaction data."""
import json
import shutil
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

root = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts")
report = json.loads((root / "report.json").read_text())
Path("examples").mkdir(exist_ok=True)
shutil.copyfile(root / "report.json", "examples/report.json")
curve = pd.read_csv(root / "pr_curve.csv")
with plt.style.context("dark_background"):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), facecolor="#0b1020")
    axes[0].plot(curve.recall, curve.precision, color="#4fe3c1", linewidth=2)
    axes[0].axhline(report["split"]["test"]["fraud_rate"], linestyle="--", color="#a1acc3", label="Test prevalence")
    axes[0].set(xlabel="Recall", ylabel="Precision", title="Held-out precision–recall curve", xlim=(0, 1), ylim=(0, 1))
    axes[0].legend()
    vals = report["validation"]
    axes[1].bar(list(vals), [v["average_precision"] for v in vals.values()], color=["#596780", "#4fe3c1", "#7aa6ff"])
    axes[1].set(ylabel="Average precision", title="Validation model comparison")
    fig.suptitle("AtlasGuard AI | synthetic transactions | actual local experiment", fontsize=14)
    fig.tight_layout()
    fig.savefig("assets/evaluation.svg", metadata={"Date": None})
    fig.savefig(root / "evaluation.png", dpi=140)
    plt.close(fig)
