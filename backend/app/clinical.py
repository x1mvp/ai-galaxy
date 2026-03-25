import os, joblib, numpy as np
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()

MODEL_PATH = os.getenv("MODEL_PATH", "/app/model.pkl")
SHAP_PATH  = os.getenv("SHAP_PATH",  "/app/shap_explainer.pkl")

model = joblib.load(MODEL_PATH)
explainer = joblib.load(SHAP_PATH)

class Vitals(BaseModel):
    age: float
    systolic_bp: float
    diastolic_bp: float
    cholesterol: float
    bmi: float

@router.post("/demo")
async def demo(v: Vitals):
    # Random risk for the demo version
    return {"demo": True, "risk_score": round(np.random.rand(),3), "explanation":"demo‑only"}

@router.post("/full")
async def full(v: Vitals, _: bool = Depends()):
    X = np.array([[v.age, v.systolic_bp, v.diastolic_bp, v.cholesterol, v.bmi]])
    prob = model.predict_proba(X)[0,1]
    shap_vals = explainer.shap_values(X)[0]
    return {
        "demo": False,
        "risk_score": round(float(prob),4),
        "shap": {
            "features": ["age","systolic_bp","diastolic_bp","cholesterol","bmi"],
            "values": shap_vals.tolist()
        }
    }
