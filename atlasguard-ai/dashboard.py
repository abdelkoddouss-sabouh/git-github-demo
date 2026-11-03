"""Run from this directory: streamlit run dashboard.py"""
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from atlasguard.data import FEATURES
from atlasguard.model import metrics

st.set_page_config(page_title="AtlasGuard AI", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background: #0b1020; color: #e8edf7;}
h1 {letter-spacing: -2px;} [data-testid='stMetric'] {background: #141e34;
padding: 20px; border-radius: 14px; border: 1px solid #263653;}
</style>""", unsafe_allow_html=True)
st.caption("ATLASGUARD / MACHINE LEARNING OBSERVATORY")
st.title("Signals become decisions.")
st.markdown("Explore how a fraud model ranks transactions, trades precision for recall, and responds to drift.")
st.warning("SYNTHETIC DATA · Educational batch lab · Not a real fraud protection service")
root = Path(os.getenv("ATLAS_ARTIFACTS", "artifacts"))
if not (root / "report.json").exists():
    st.info("Run python -m atlasguard.pipeline --rows 100000 first, then refresh.")
    st.stop()


@st.cache_data
def read_run(path, report_mtime, scores_mtime):
    return json.loads((Path(path) / "report.json").read_text()), pd.read_parquet(Path(path) / "test_scores.parquet")


report, data = read_run(str(root), (root / "report.json").stat().st_mtime_ns,
                        (root / "test_scores.parquet").stat().st_mtime_ns)
with st.sidebar:
    st.header("Decision controls")
    threshold = st.slider("Alert threshold", 0.0, 1.0, float(report["threshold"]), .005)
    st.caption("Moving this slider explores the test set. Published metrics keep the validation-selected threshold.")
    st.metric("Selected model", report["winner"])
    st.write("Selection: validation average precision")
    st.caption("Costs below are hypothetical user inputs; they are not calibrated business costs.")
    false_alert_cost = st.number_input("Cost per false alert (units)", min_value=0.0, value=1.0)
    missed_fraud_cost = st.number_input("Cost per missed fraud (units)", min_value=0.0, value=20.0)

m = metrics(data.is_fraud, data.risk_score, threshold)
cols = st.columns(4)
for col, name, value in zip(cols, ["Test average precision", "Precision", "Recall", "Alerts"],
                           [f'{m["average_precision"]:.3f}', f'{m["precision"]:.1%}',
                            f'{m["recall"]:.1%}', f'{m["alerts"]:,}']):
    col.metric(name, value)
overview, decisions, monitoring, learn = st.tabs(["Model performance", "Transaction review", "Drift monitor", "Understand the system"])
with overview:
    left, right = st.columns(2)
    curve = pd.read_csv(root / "pr_curve.csv")
    fig = px.line(curve, x="recall", y="precision", title="Held-out precision–recall curve", template="plotly_dark")
    fig.add_hline(y=float(data.is_fraud.mean()), line_dash="dash", annotation_text="Test prevalence")
    left.plotly_chart(fig, width="stretch")
    matrix = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
    right.plotly_chart(px.imshow(matrix, text_auto=True, x=["No alert", "Alert"],
                                 y=["Legitimate", "Fraud"], title="Confusion matrix", template="plotly_dark"), width="stretch")
    st.subheader("Validation leaderboard — used for model selection")
    st.dataframe(pd.DataFrame(report["validation"]).T, width="stretch")
    st.metric("Illustrative total error cost", f'{m["fp"] * false_alert_cost + m["fn"] * missed_fraud_cost:,.0f} units')
    st.caption("Accuracy alone hides rare fraud. Average precision assesses ranking; precision and recall assess one threshold.")
with decisions:
    st.subheader("Highest-scored test transactions")
    table = data.sort_values("risk_score", ascending=False).head(200).copy()
    table["alert"] = table.risk_score >= threshold
    st.dataframe(table, width="stretch", hide_index=True)
    st.download_button("Download review queue (CSV)", table.to_csv(index=False), "review_queue.csv", "text/csv")
    st.subheader("Which inputs help the model rank risk?")
    imp = pd.DataFrame({"feature": FEATURES, "AP decrease on shuffle":
                        [report["permutation_importance_validation"][x] for x in FEATURES]})
    st.plotly_chart(px.bar(imp.sort_values("AP decrease on shuffle"), x="AP decrease on shuffle", y="feature",
                          orientation="h", template="plotly_dark"), width="stretch")
    st.caption("Global validation permutation importance; not a causal explanation or an explanation of one transaction.")
with monitoring:
    psi = pd.DataFrame({"feature": FEATURES, "PSI": [report["drift_psi"][x] for x in FEATURES]})
    st.plotly_chart(px.bar(psi, x="feature", y="PSI", template="plotly_dark", title="Train-to-test feature distribution change"), width="stretch")
    st.caption("PSI uses training quantiles and smoothed counts. It describes distribution change; it does not prove model failure.")
    st.json(report["split"])
with learn:
    st.markdown("""### Follow one transaction
1. A seeded generator creates synthetic input features and a stochastic fraud label.
2. Chunks are stored as Parquet files. DuckDB computes totals and selects a bounded sample.
3. The earliest 60% trains models, the next 20% selects the model and threshold.
4. The latest 20% evaluates the frozen choice, including a distribution shift.
5. FastAPI serves the same saved model; this dashboard explores held-out scores.

**No target leakage:** the label, transaction ID and timestamp are excluded from model inputs.
The target is assumed available for offline evaluation; real fraud labels can arrive late.
See `docs/APPRENDRE.md` for the French learning path and `MODEL_CARD.md` for limitations.
""")
    st.json({"lake": report["lake"], "sample_rows": report["sample_rows"], "versions": report["versions"]})
