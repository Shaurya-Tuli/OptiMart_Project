# OptiMart — AI-Powered Surplus Food Redistribution & Expiration Platform

OptiMart is an intelligent surplus food management and redistribution ecosystem: FastAPI + Postgres/PostGIS + Redis + Celery, running under Docker Compose.

## 🚀 Quick Start

```bash
# 1. Environment setup
cp .env.example .env

# 2. Build and start containers
docker compose up --build -d

# 3. Verify health check
curl http://localhost:8000/health
# -> {"database":"ok","redis":"ok","healthy":true}

# 4. Run automated test suite (pytest + coverage)
docker compose exec api pytest -v --cov=app
```

## 📦 Services Overview

| Service | Container | Internal Port | Host Port |
|---|---|---|---|
| FastAPI API | optimart-api | 8000 | 8000 |
| Celery Worker | optimart-worker | - | - |
| Postgres + PostGIS | optimart-db | 5432 | 5432 |
| Redis | optimart-redis | 6379 | 6379 |

## 🛠️ API Reference

### Phase 1 — Inventory Core
- **Stores**: `POST /api/v1/stores`, `GET /api/v1/stores`, `GET /api/v1/stores/{id}`, `PUT /api/v1/stores/{id}`, `DELETE /api/v1/stores/{id}`
- **Batches**: `POST /api/v1/inventory/batches`, `GET /api/v1/inventory/batches`, `GET /api/v1/inventory/batches/{id}`, `PUT /api/v1/inventory/batches/{id}`, `DELETE /api/v1/inventory/batches/{id}`
- **Bulk CSV Upload**: `POST /api/v1/inventory/upload-csv`

### Phase 2 — ML Expiration Risk & Dynamic Discounting
- `POST /api/v1/ml/predict-discount` — Predict risk score (0.0–1.0) and optimal discount percentage for item features.
- `POST /api/v1/ml/reprice-batch/{batch_id}` — Evaluate batch expiration risk, fetch weather temperature, apply ML discount & current price in PostgreSQL DB.
- `POST /api/v1/ml/train` — Trigger on-demand retraining of the Scikit-Learn ML pricing model.

## 🧪 Testing

```bash
# Run pytest in container
docker compose exec api pytest -v --cov=app
```

## 📋 Documentation
- [STATUS.md](STATUS.md) — Implementation roadmap & phase completion checklist
- [DECISIONS.md](DECISIONS.md) — Architecture decision records

