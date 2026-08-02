# OptiMart Project Status

## Current Phase: Phase 15 (Category Intelligence & Cycle-Aware Forecasting) COMPLETED

### Phase 15 Summary
Phase 15 builds a synchronized Category Intelligence View inside the Retailer Portal's "Demand & Reorder" tab, displaying end-to-end demand forecasting metrics per product category.

- **Category-Dashboard API (`app/api/category_dashboard.py`)**: Adds two read-only endpoints returning simulated inventory timelines (qty_on_hand over time showing customer consumption dips and restock peaks) and aligned actual vs naive vs Model D forecasts.
- **Cycle-Aware Forecasting Markers**: Draws visual cycle markers on the forecast timeline indicating Order Placement (Day N), Replenishment Arrival (Day N+7), and Forecast Horizon (Day N+14) to illustrate lead-time dynamics.
- **Credibility / Naive Baseline Comparison**: Renders the 7-day moving average naive baseline alongside Model D forecasts, surfacing validation MAE metrics to prove forecast credibility.
- **Demo Data Seed Extension (`scripts/seed_demo_phase15.py`)**: Seeded 6 opening category batches (Dairy, Bakery, Fruits & Veggies, Meat & Seafood, Snacks, Food Grains) at Store 1 with qty=30 on 2026-07-27, and extended sales history to today to avoid cold-start fallbacks.
- **Testing**: All 51 automated tests passing.

### Phase 14 Summary
Phase 14 introduces a dual role landing screen (Retailer vs. Customer) and a dedicated Customer Marketplace Feed showing live expiring food discounts.

- **Role Selection Overlay (`app/static/index.html`)**: Added a glassmorphic full-screen overlay for users to choose their role on load. Hides/shows operational vs. customer views based on selection, with persistent `localStorage` auto-login.
- **Customer Feed Layout**: Reusable product card grid displaying live discounted items from the backend (`/api/v1/inventory/batches`). Includes text search, store location dropdowns, and category buttons (Dairy, Bakery, Fruits, Meat, Others) using category-themed gradients.
- **Claim Checkout Modal**: Direct checkout modal supporting self-pickup, delivery, or subsidized NGO bypass (with NGO Gov ID details, setting cost to ₹0). Simulates multi-rail payment checkout (Razorpay/Stripe) by reserving the batch (`POST /api/v1/claims`) and capturing the payment status (`PATCH /api/v1/claims/{token}` with `PAID`), updating marketplace cache instantly.
- **Switch Role Action**: A top header button allows users to toggle between Retailer and Customer portals seamlessly.
- **Testing**: 51 automated tests passing across all backend endpoints.

### Phase 13 Summary
Phase 13 is the demo rehearsal & submission hardening phase (Playbook Ch. 14.1 / Ch. 14.2). No new backend code — the deliverables are the complete demo run-of-show, Q&A prep, and a final accuracy pass on all source citations.

- **[`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md)**: Full extended run-of-show (5–5.5 min) following Ch. 14.1's sequence: loop diagram open → Demand & Reorder tab → connective-tissue beat (1:00–1:15) → Volume I hand-off → Eco-Impact close. Includes backup recording plan and pre-demo checklist.
- **[`QA_PREP.md`](./QA_PREP.md)**: Rehearsed answers to six anticipated judge questions. The Ch. 14.2 Q&A answer (*"How do you validate a forecast when you can't wait a week?"*) is prepared with honest framing: *"the pipeline is real and swappable; the specific numbers demonstrate the mechanism, not a production-accuracy claim."*
- **[`SOURCES.md`](./SOURCES.md)**: Final accuracy pass — added citations for Phases 9–13 (Scikit-Learn HistGBR, Chart.js, safety-stock literature, AI-assistance disclosure filled in).
- **Testing**: 51 automated tests passing across all phases, zero regressions.

### Phase 10 Summary
Phase 10 implements the reorder recommendation logic, translating Model D's demand forecasts into optimal ordering recommendations for retailers, accounting for safety stock and on-hand inventory.

- **Model & Table (`app/models/reorder_recommendation.py`)**: `ReorderRecommendation` model with composite unique constraint `(store_id, sku, forecast_run_date)` storing predictions, recommended order quantity, top factors, and the retailer's decision.
- **Service Layer (`app/services/reorder_recommendation.py`)**: Computes safety stock buffers scaling inversely with prediction confidence:
  `safety_stock_buffer = predicted_demand * base_pct * (2.0 - confidence)`
  `recommended_qty = max(0, int(predicted_demand + safety_stock_buffer - current_qty_on_hand))`
  Handles retailer decisions: `ACCEPTED`, `DISMISSED`, or `ADJUSTED` (with validation for `adjusted_qty`).
- **REST Endpoints (`app/api/forecast_routes.py`)**:
  - `POST /api/v1/forecast/generate/{store_id}`: Trigger recommendation run.
  - `GET /api/v1/forecast/{store_id}`: Retrieve recommendations.
  - `POST /api/v1/forecast/recommendations/{id}/decision`: Record retailer decision.
- **Celery Task (`app/tasks/forecasting.py`)**: Background task `run_weekly_forecast_task` to generate/refresh recommendations for all stores.
- **Testing**: 50 total test suites passing across all phases (including `tests/test_reorder_recommendation.py`).

### Phase 11 Summary
Phase 11 adds the **Demand & Reorder** tab to the existing retailer dashboard — the primary visual deliverable for the forecasting volume. Retailers can now see, interpret, and act on Model D predictions directly from the dashboard.

- **New Tab: Demand & Reorder** (`app/static/index.html`): Full tab panel with store selector, Run Forecast button, 4-KPI strip (SKUs Forecasted, Total Recommended, Accepted, Pending), recommendation table, and interactive trend chart.
- **Recommendation Table**: Per-SKU rows showing predicted demand (7d), confidence band (p10–p90), recommended reorder quantity, decision status badge, and inline ✓ Accept / ↕ Adjust / ✕ Dismiss controls backed by live API calls to `POST /api/v1/forecast/recommendations/{id}/decision`.
- **Trend Chart (Actual vs Forecast)**: Click any row to render a 3-series Chart.js line chart — Actual Sales (28 days), Naive Baseline (7-day rolling average), and Model D Forecast (next 7 day projection) — the playbook's Ch. 9.2 "forecast-vs-actual overlay" demo visual.
- **"Why" Explanations**: Each selected SKU shows the top contributing factors panel (e.g. "Upcoming weekend demand spike") directly below the chart — fulfilling playbook Ch. 9.2 for interpretable recommendations.
- **Confidence Band Callout**: Visual p10→p90 gradient bar with labeled range values.
- **Light/Dark Theme**: Chart colors and backgrounds adapt dynamically when theme is toggled.
- **Testing**: 50 total test suites passing (Phase 11 is frontend-only, no backend changes).

### Phase 12 Summary
Phase 12 closes the feedback loop between **Model D** (demand forecasting) and **Model A** (dynamic markdown pricing), delivering the "connective tissue" behavior described in Playbook Ch. 14.1.

- **Closed-Loop Logic (`app/ml/predictor.py`)**: `PricingPredictor.predict()` now accepts optional `store_id`, `sku`, and `db` parameters. When provided, it queries the latest `ReorderRecommendation` and sums actual sales from `sales_history` over the most recent 7-day window. If actual sales are less than **70% of the predicted demand**, the SKU is flagged as under-performing: `risk_score` is boosted by `+0.25` (capped at `1.0`) and the reasoning tag `forecast_underperformance_detected` is added to the prediction output.
- **API Integration (`app/api/pricing.py`)**: The `POST /api/v1/ml/reprice-batch/{batch_id}` endpoint now passes `store_id`, `sku`, and `db` into `predict()`, enabling the live loop check on every reprice call.
- **Schema (`app/schemas/pricing.py`)**: `BatchRepriceResponse` now includes a `reasoning_tags: list[str]` field so the frontend can react to signals from the model.
- **UI (`app/static/index.html`)**:
  - **Active Batches table**: New "Actions" column with an ⚡ **Reprice** button per row. Clicking it calls `repriceBatchUI()`, which POSTs to the reprice endpoint, checks `reasoning_tags`, and shows a warning toast if underperformance was detected.
  - **Dynamic Discounting Simulation**: The recommendation result card now shows a "System Signals & Logic" badges strip (amber `⚠️ Sales Under-performing Forecast (+25% Risk)` badge when triggered).
- **Test Suite (`tests/test_loop_integration.py`)**: End-to-end integration test creates a store, batch, forecast recommendation, and two sales history scenarios (performing: 84 units vs. under-performing: 28 units) to validate the markdown boost and reasoning tag assertion.
- **Testing**: 51 total test suites passing (1 new: `test_loop_integration.py`).


Phase 9 implements **Model D** — the gradient-boosted demand forecasting engine predicting 7-day expected unit demand per store/SKU with calibrated confidence bands.

- **Model D (`app/ml/forecaster.py`)**: `DemandForecaster` class using Scikit-Learn `HistGradientBoostingRegressor` trained at three quantiles (10th/50th/90th percentile), with `min_periods=1` rolling lag features (`lag_7d`, `lag_14d`, `lag_28d`, `rolling_avg_7d`, `rolling_avg_28d`), temporal signals (`day_of_week`, `is_weekend`), and contextual flags (`promotion_flag`, `stockout_flag`, `stockout_rate_recent`).
- **Cold-Start Fallback**: Category-level mean demand fallback for stores/SKUs with <14 days of history.
- **Baseline Benchmark**: Naive 7-day moving average MAE computed during training for interpretability.
- **REST Endpoints (`app/api/forecasting.py`)**:
  - `POST /api/v1/forecast/train`: Trains/retrains Model D against live `sales_history` data.
  - `GET /api/v1/forecast/predict`: Returns `predicted_demand_next_7d`, `confidence_low`, `confidence_high`, `confidence_band_spread`, and `top_factors` for any store/SKU.
- **Live Results** (against 13,104 sales history rows): 10,658 train samples, baseline MAE 11.74, Model D MAE 10.97 (6.51% improvement over baseline).
- **Testing**: 47 total test suites passing across all phases (including `tests/test_forecasting.py`).

### Phase 8 Summary
Phase 8 establishes the historical sales data pipeline essential for demand forecasting (Model D). It introduces the `sales_history` database table, Pydantic schemas, service layer with upsert capabilities, REST endpoints (including POS CSV bulk upload), synthetic data generation script, and test suite.

- **Model & Table (`app/models/sales_history.py`)**: `SalesHistory` model with `store_id`, `sku`, `date`, `units_sold`, `price_at_time`, `promotion_flag`, `stockout_flag`, and a unique constraint on `(store_id, sku, date)`.
- **Service Layer (`app/services/sales_history.py`)**: Concurrency-safe single and bulk upserts (`on_conflict_do_update` using `index_elements` for PostgreSQL and SQLite test compatibility) and filtered history retrieval.
- **REST Endpoints (`app/api/sales_history.py`)**:
  - `POST /api/v1/sales-history`: Record daily sales entry.
  - `POST /api/v1/sales-history/bulk`: Bulk record sales entries.
  - `GET /api/v1/sales-history`: Query historical sales records with store, SKU, and date range filters.
  - `POST /api/v1/sales-history/upload-csv`: Bulk import daily sales CSV file.
- **Synthetic Data Generator (`scripts/generate_sales_history.py`)**: Generates 16 weeks of daily historical sales data (~13,328 rows) incorporating day-of-week seasonality (weekend spikes), periodic promotions, and stockout noise.
- **Testing**: 44 total test suites passing across all phases (including `tests/test_sales_history.py`).

### Phase 9 Summary
Phase 9 implements **Model D** — the gradient-boosted demand forecasting engine predicting 7-day expected unit demand per store/SKU with calibrated confidence bands.

- **Model D (`app/ml/forecaster.py`)**: `DemandForecaster` class using Scikit-Learn `HistGradientBoostingRegressor` trained at three quantiles (10th/50th/90th percentile), with `min_periods=1` rolling lag features (`lag_7d`, `lag_14d`, `lag_28d`, `rolling_avg_7d`, `rolling_avg_28d`), temporal signals (`day_of_week`, `is_weekend`), and contextual flags (`promotion_flag`, `stockout_flag`, `stockout_rate_recent`).
- **Cold-Start Fallback**: Category-level mean demand fallback for stores/SKUs with <14 days of history.
- **Baseline Benchmark**: Naive 7-day moving average MAE computed during training for interpretability.
- **REST Endpoints (`app/api/forecasting.py`)**:
  - `POST /api/v1/forecast/train`: Trains/retrains Model D against live `sales_history` data.
  - `GET /api/v1/forecast/predict`: Returns `predicted_demand_next_7d`, `confidence_low`, `confidence_high`, `confidence_band_spread`, and `top_factors` for any store/SKU.
- **Live Results** (against 13,104 sales history rows): 10,658 train samples, baseline MAE 11.74, Model D MAE 10.97 (6.51% improvement over baseline).
- **Testing**: 47 total test suites passing across all phases (including `tests/test_forecasting.py`).

### Post-Phase 7 Maintenance
- Restored the OptiMart Assistant API and dashboard chat widget after they were absent from the active discount-engine branch. The widget now loads live discounted batches and supports category, claiming, payment, safety, and help queries.
- Restored the light/dark theme toggle. The choice is persisted in local storage and dashboard charts update their foreground and grid colors with the selected theme.
- Verification: focused assistant and analytics tests pass; live `/api/v1/assistant/deals` and `/api/v1/assistant/chat` endpoints return current deal data.
- Known unrelated test failure: `tests/test_payments.py::test_razorpay_webhook_updates_claim` currently receives HTTP 400 where the test expects HTTP 200. No payment code changed in this maintenance repair.

### Phase 7 Summary
Phase 7 delivers the Analytics & Waste Reduction Dashboard, quantifying environmental impact (food waste prevented in kg, CO2 emissions offset in kg), financial recovery metrics, NGO standing order allocations, and claim conversion rates across individual stores and platform-wide.

- **Analytics Service** (`app/services/analytics.py`): Platform-wide and store-specific metrics aggregation for waste reduction (0.5 kg waste / item rescued), CO2e savings (2.5 kg CO2e / kg food waste), revenue recovered, and NGO subsidized allocations.
- **REST Endpoints**:
  - `GET /api/v1/analytics/summary`: Platform-wide waste impact, financial recovery, CO2 savings, and NGO metrics.
  - `GET /api/v1/analytics/store/{store_id}`: Store-level breakdown of active, expired, and rescued batches with total revenue recovered.
- **Testing**: 36 total test suites passing across all 7 phases.

### Phase 6 Summary
Phase 6 implements the Multi-rail Payment engine supporting both Razorpay (INR/paise) and Stripe (USD/cents) checkout flows, signature-verified webhooks, and an automatic payment bypass for subsidized NGO/shelter allocations.

- **Payment Service** (`app/services/payment.py`): Multi-provider checkout order creation (Razorpay Orders API & Stripe Checkout Sessions) with automatic mock fallback when live credentials are not supplied. Webhook HMAC signature verification for both rails.
- **Subsidized NGO Bypass**: NGO standing order allocations marked `is_subsidized=True` skip payment processing completely, immediately resolving to status `PAID` with payment reference `SUBSIDIZED_BYPASS`.
- **REST Endpoints**:
  - `POST /api/v1/payments/checkout-session`: Initiate Razorpay or Stripe payment for a reserved claim.
  - `POST /api/v1/payments/webhooks/razorpay`: Handle Razorpay `payment.captured` webhooks & transition claim to `PAID`.
  - `POST /api/v1/payments/webhooks/stripe`: Handle Stripe `checkout.session.completed` webhooks & transition claim to `PAID`.
- **Testing**: 32 total test suites passing across all phases.

### Phase 5 Summary
Phase 5 implements the Consumer Marketplace with geo-fenced batch discovery and high-concurrency Redis TTL reservation locking for atomic claim management.

- **Claim Model** (`app/models/claim.py`): Tokenized claim records with `claim_token`, `reserved_until` TTL timestamp, `fulfillment_type` (pickup/delivery), `status` (RESERVED/PAID/FULFILLED/CANCELLED), and `is_subsidized` flag for NGO bypass.
- **Redis Reservation Lock** (`app/services/reservation.py`): Atomic `SET NX EX` Redis key per batch — single source of truth for concurrency safety, auto-released on payment confirmation or expiry.
- **PostGIS Geo-fenced Search** (`app/services/geo_routing.py`): `ST_DWithin` geography query returning nearby active/discounted batches within a configurable radius (km) with Python haversine fallback.
- **REST Endpoints**:
  - `POST /api/v1/claims/geo-search`: Geo-fenced marketplace search by lat/lng + radius.
  - `POST /api/v1/claims`: Create tokenized reservation with Redis TTL lock.
  - `GET /api/v1/claims/{token}`: Resolve a tokenized claim link.
  - `GET /api/v1/claims/batch/{batch_id}`: Fetch active reservation for a batch.
  - `PATCH /api/v1/claims/{token}`: Update claim status (e.g., PAID, FULFILLED).
  - `GET /api/v1/claims/lock-status/{batch_id}`: Inspect Redis reservation lock.
- **Testing**: 27 total test suites passing across all phases.

### Phase 3 Summary
Phase 3 implements the Notification Engine using Twilio (SMS & WhatsApp Business API), enabling hyper-local flash sale alerts, background broadcast dispatch, and single-tap "reply YES" SMS claiming.

- **Notification Service**: `TwilioNotificationService` in `app/services/notification.py` handling SMS dispatch, WhatsApp messaging, and batch flash-sale broadcasts (with automatic mock fallback when live credentials are not set).
- **Asynchronous Worker Tasks**: Celery background task `dispatch_batch_notifications_task` in `app/tasks/dispatch.py`.
- **REST Endpoints**:
  - `POST /api/v1/notifications/send`: Outbound SMS or WhatsApp dispatch to a recipient.
  - `POST /api/v1/notifications/broadcast/{batch_id}`: Trigger hyper-local flash sale broadcast.
  - `POST /api/v1/notifications/twilio-inbound`: Handle inbound Twilio webhooks for single-tap "reply YES" claiming.
- **Testing**: 17 total test suites passing across inventory, ML pricing, standing orders, and notifications.

---

## Phase Roadmap Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Docker & Postgres/Redis Infrastructure | ✅ Completed |
| Phase 1 | Inventory Core (Stores, Batches, CSV Upload) | ✅ Completed |
| Phase 2 | ML Expiration Risk Model & Dynamic Discounting | ✅ Completed |
| Phase 3 | Notification Engine (SMS, WhatsApp, Twilio) | ✅ Completed |
| Phase 4 | Standing Order Engine (NGO & Shelter priority) | ✅ Completed |
| Phase 5 | Consumer Marketplace & Geo-routing | ✅ Completed |
| Phase 6 | Multi-rail Payments (Stripe & Razorpay) | ✅ Completed |
| Phase 7 | Analytics Dashboard & Final Hardening | ✅ Completed |
