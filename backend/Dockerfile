# ---------- Build stage ----------
FROM python:3.12-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------- Runtime stage ----------
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY backend/app ./app

# OPTIONAL: copy model files if you have them (keep them <100 MB)
# COPY backend/model.pkl ./model.pkl
# COPY backend/shap_explainer.pkl ./shap_explainer.pkl
# COPY backend/bert.onnx ./bert.onnx

EXPOSE 8080
ENV PORT=8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
