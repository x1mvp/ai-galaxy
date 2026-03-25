import os, numpy as np, onnxruntime as ort
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from transformers import AutoTokenizer

router = APIRouter()

ONNX_PATH = os.getenv("ONNX_PATH", "/app/bert.onnx")
TOKENIZER = os.getenv("TOKENIZER","distilbert-base-uncased")

if not os.path.exists(ONNX_PATH):
    raise RuntimeError("Missing ONNX model – see README for conversion steps.")

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)
session   = ort.InferenceSession(ONNX_PATH, providers=["CPUExecutionProvider"])

LABELS = ["spam","news","tech","sports","finance"]

class TextPayload(BaseModel):
    text: str

def predict(text: str):
    inputs = tokenizer(text, truncation=True, padding="max_length",
                     max_length=128, return_tensors="np")
    ort_inputs = {k: v.astype(np.int64) for k, v in inputs.items()}
    logits = session.run(None, ort_inputs)[0]   # (1, n_labels)
    probs = 1/(1+np.exp(-logits.squeeze()))   # sigmoid → multi‑label
    results = [{"label": LABELS[i], "prob": round(float(probs[i]),3)} for i in range(len(LABELS))]
    return sorted(results, key=lambda x:x["prob"], reverse=True)[:5]

DEMO_OUT = [
    {"label":"spam","prob":0.87},
    {"label":"news","prob":0.71},
    {"label":"tech","prob":0.62}
]

@router.post("/demo")
async def demo(_: TextPayload):
    return {"demo": True, "predictions": DEMO_OUT}

@router.post("/full")
async def full(payload: TextPayload, _: bool = Depends()):
    preds = predict(payload.text)
    return {"demo": False, "predictions": preds}
