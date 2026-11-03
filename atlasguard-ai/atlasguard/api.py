"""Local prediction API. Load only model.joblib files you created and trust."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from .data import FEATURES


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    amount: float = Field(ge=0, le=10000000)
    hour: int = Field(ge=0, le=23, strict=True)
    distance_km: float = Field(ge=0, le=50000)
    attempts_1h: int = Field(ge=0, le=10000, strict=True)
    account_age_days: int = Field(ge=0, le=50000, strict=True)
    international: int = Field(ge=0, le=1, strict=True)
    new_device: int = Field(ge=0, le=1, strict=True)


@asynccontextmanager
async def lifespan(app):
    path = Path(os.getenv("ATLAS_ARTIFACTS", "artifacts")) / "model.joblib"
    app.state.bundle = joblib.load(path) if path.exists() else None
    yield


app = FastAPI(title="AtlasGuard AI", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ready" if getattr(app.state, "bundle", None) else "model_missing"}


@app.post("/predict")
def predict(transaction: Transaction):
    bundle = getattr(app.state, "bundle", None)
    if bundle is None:
        raise HTTPException(503, "Generate local artifacts first")
    frame = pd.DataFrame([transaction.model_dump()])[FEATURES]
    score = float(bundle["model"].predict_proba(frame)[0, 1])
    return {"risk_score": score, "alert": score >= bundle["threshold"],
            "threshold": bundle["threshold"], "training_source": bundle["source"],
            "notice": "Educational model; not a production fraud decision"}
