# Architecture Decision Records (ADR)

## ADR 001: Project Rebranding to NEXPIRE
- **Context**: Project named ResQ-Chain renamed to NEXPIRE across codebase, configuration, and documentation.
- **Decision**: Update all docker service names, environment variables, documentation, and API metadata to `NEXPIRE`.
- **Status**: Implemented & Verified.

## ADR 010: Sales History & Synthetic Data Pipeline (Phase 8)
- **Context**: Demand forecasting (Model D) requires historical daily SKU sales data with price, promotional, and stockout signals.
- **Decision**:
  - `SalesHistory` model with composite unique constraint `(store_id, sku, date)`.
  - SQLAlchemy `on_conflict_do_update` using `index_elements` to ensure upserts work identically on production PostgreSQL and SQLite test environments.
  - CSV upload endpoint `POST /api/v1/sales-history/upload-csv` using standard `csv.DictReader` for POS data ingestion.
  - Synthetic data script (`scripts/generate_sales_history.py`) generating 16 weeks of daily sales data (~13,328 records) with reproducible seeds, day-of-week seasonality, promotional spikes, and stockout noise.
- **Status**: Implemented & Verified.
- **Source**: Original to this hackathon (Volume II Demand Forecasting extension).

## ADR 002: Inventory Core Architecture (Phase 1)
- **Context**: Need high-throughput CRUD for retail store inventory management and bulk CSV imports.
- **Decision**: 
  - Use SQLAlchemy ORM with PostgreSQL backend for persistent storage.
  - Implement Pydantic v2 schemas for strict request/response data validation.
  - Automatic `current_price` calculation based on `discount_percentage` when `current_price` is omitted.
  - Streamed CSV parsing using standard library `csv.DictReader` and row-level rollback handling to return clear import error diagnostics without failing valid rows.
- **Status**: Implemented & Verified.

## ADR 003: ML Expiration Risk & Dynamic Discount Architecture (Phase 2)
- **Context**: Need automated, objective price markdown recommendations based on perishable food timelines, stock volumes, margin constraints, and environmental factors.
- **Decision**:
  - Scikit-Learn Multi-Output `RandomForestRegressor` pipeline preprocessed with `ColumnTransformer` (StandardScaler + OneHotEncoder).
  - Synthetic food batch training data generator (`app/ml/synthetic_data.py`) to ensure deterministic offline training capability.
  - Model serialization using `joblib` stored at `app/ml/artifacts/pricing_model.joblib`.
  - Automatic initial training on app startup if artifact is missing.
  - Ambient temperature integration via `app/services/weather.py` (OpenWeather API with 25.0°C default fallback).
- **Status**: Implemented & Verified.

## ADR 004: Standing Order Engine & NGO Priority Allocation (Phase 4)
- **Context**: Shelters and NGOs require reliable, priority access to expiring food batches without competing in consumer payment loops.
- **Decision**:
  - Implement rule-based `StandingOrder` subscription model (`category_filter`, `min_quantity`, `priority_window_hours`).
  - Create dedicated `StandingOrderMatch` priority allocation entities (`is_subsidized=True`, `status="RESERVED"`), bypassing payment processing entirely for shelter claims.
  - Provide automated evaluation trigger endpoint (`POST /api/v1/standing-orders/evaluate`) to scan candidate active/discounted batches against standing order rules.
- **Status**: Implemented & Verified.

## ADR 005: Notification Engine Architecture & Inbound SMS Claiming (Phase 3)
- **Context**: Need hyper-local outbound flash-sale notification dispatch (SMS & WhatsApp via Twilio) and frictionless inbound SMS reply claiming ("reply YES").
- **Decision**:
  - Implement `TwilioNotificationService` (`app/services/notification.py`) supporting both SMS and WhatsApp channels.
  - Automatic fallback to mock message IDs when Twilio API credentials are unset or invalid in local testing.
  - Inbound Twilio webhook handler (`POST /api/v1/notifications/twilio-inbound`) parsing "YES" or "CLAIM <batch_id>" to automatically reserve food rescue items.
  - Asynchronous background dispatch task `dispatch_batch_notifications_task` in `app/tasks/dispatch.py` for Celery worker execution off the HTTP request path.
- **Status**: Implemented & Verified.

## ADR 006: Consumer Marketplace, Geo-routing & Redis TTL Locking (Phase 5)
- **Context**: Consumers need a frictionless one-link claim flow with concurrency-safe reservations; geo-fenced discovery ensures alerts only reach reachable buyers.
- **Decision**:
  - `Claim` model with unique `claim_token` (URL-safe random) as the tokenized single-use claim link.
  - Redis `SET NX EX` key `claim:lock:{batch_id}` as the single source of truth for batch reservation — prevents double-claiming under simultaneous alerts without a database lock.
  - `ST_DWithin` PostGIS geography query for O(log n) radius search; Python haversine fallback for SQLite test environments.
  - `reserved_until` timestamp stored on the claim row for persistence; Redis TTL is the enforcement gate.
- **Status**: Implemented & Verified.

## ADR 007: Multi-rail Payments (Stripe & Razorpay) (Phase 6)
- **Context**: NEXPIRE operates across regions requiring regional payment gateway integration (Razorpay for India/INR, Stripe for North America & Global/USD) plus non-commercial bypass for food banks.
- **Decision**:
  - Unified checkout endpoint `POST /api/v1/payments/checkout-session` routing to Razorpay Orders API or Stripe Checkout Sessions based on request parameters/region.
  - Automatic payment bypass for claims flag `is_subsidized=True` — instantly transitions claim to `PAID` with `payment_ref="SUBSIDIZED_BYPASS"`.
  - Signature-verified webhooks for both gateways (`/webhooks/razorpay` and `/webhooks/stripe`) to atomically transition claims from `PENDING_PAYMENT` to `PAID` and release Redis reservation locks.
- **Status**: Implemented & Verified.

## ADR 008: Analytics & Waste Reduction Dashboard (Phase 7)
- **Context**: Stakeholders, grocery partners, and NGOs require transparent reporting on food waste averted, CO2 offset, financial revenue recovered, and NGO allocation conversion rates.
- **Decision**:
  - `get_analytics_summary` aggregates platform metrics using standardized conversion factors (0.5 kg waste / item rescued; 2.5 kg CO2e / kg waste).
  - Store-specific analytics endpoint `/api/v1/analytics/store/{store_id}` delivers per-store breakdown of active, expired, and rescued inventory.
- **Status**: Implemented & Verified.

## ADR 009: Local Rule-Based Assistant and Persisted Theme Preference
- **Context**: The dashboard referenced an AI assistant and light-mode controls that were missing from the active application branch, causing assistant API requests to return 404 and leaving no usable theme switch.
- **Decision**:
  - Register the local, rule-based assistant router at `/api/v1/assistant`; it provides deterministic product discovery and FAQs without requiring an external LLM service or credentials.
  - Restore the dashboard assistant widget and light/dark theme toggle, persisting the user preference in `localStorage` and updating Chart.js colors on change.
- **Status**: Implemented & Verified.



