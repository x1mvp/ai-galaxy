import os
from fastapi import FastAPI, Depends, Header, HTTPException
from . import crm, fraud, clinical, nlp

app = FastAPI(title="AI Galaxy – Unified Back‑End")

FULL_PASSWORD = os.getenv("FULL_PASSWORD", "galaxy2026")

def require_password(pwd: str = Header(...)):
    if pwd != FULL_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    return True

app.include_router(crm.router, prefix="/CRM")
app.include_router(fraud.router, prefix="/Fraud")
app.include_router(clinical.router, prefix="/Clinical")
app.include_router(nlp.router, prefix="/NLP")

@app.get("/healthz")
async def health():
    return {"status": "ok"}
