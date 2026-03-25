# 🌌 AI Galaxy – Four AI Demos in One Repo

## What you’ll see
* A **galaxy‑themed landing page** (`https://<user>.github.io`) where each planet is a demo.
* A **single FastAPI service** on **Google Cloud Run** that powers all four demos.
* **Password‑gated “full version”** – type `galaxy2026` (or your own secret) to unlock the real model output.
* **CI/CD** – every push rebuilds the site, the Docker image, and updates the planet URLs automatically.

## Quick start (local)
```bash
# front‑end
cd frontend && python -m http.server 8080

# back‑end (needs Docker)
cd ../backend
docker build -t ai-galaxy .
docker run -e FULL_PASSWORD=galaxy2026 -p 8080:8080 ai-galaxy
