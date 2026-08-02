# ARCHITECTURE.md — OptiMart Technical Architecture

This document is the technical reference companion to `README.md`. It describes the system at the
level a new engineer (or agent) needs to be productive without re-deriving design decisions from
scratch. For *why* certain choices were made, cross-reference `DECISIONS.md`.

---

## 1. System Overview — Three Planes

OptiMart is best understood as three cooperating planes rather than one monolith. Keeping this
separation explicit in the codebase (not just conceptually) is what lets phases be built and demoed
independently per `RULES.md`.

| Plane | Responsibility | Core components |
|---|---|---|
| **1. Data &amp; Prediction** | Ingests inventory/batch data, enriches with weather &amp; demand history, runs the ML markdown engine, decides price + target segment. | PostgreSQL + PostGIS, Scikit-Learn model (Joblib), Celery beat scheduled scans |
| **2. Orchestration** | Business logic: reservations, locking, payment state machine, standing-order routing, reliability scoring. | FastAPI, Redis (cache + broker + TTL locks), Celery workers |
| **3. Delivery** | Everything the human on the other end sees or receives. | Twilio (SMS + WhatsApp), Stripe/Razorpay checkout, React claim page &amp; dashboards, WebSocket live-price feed |

**Event loop, in one sentence:** a scheduled scan finds at-risk batches → the model prices and segments
them → if a threshold is breached, an alert fires to a geofenced audience → a claim reserves stock with
a TTL lock → payment confirms the reservation → fulfillment (pickup/delivery) executes → the outcome
(sold, expired, donated) feeds back into training data for the next model refresh.

---

## 2. Client-Side Architecture

| Surface | Stack | Notes |
|---|---|---|
| Public Claim Page | React + Tailwind, no auth | Opened from SMS/WhatsApp link or scanned QR code. Shows item, discounted price, reservation countdown, pickup/delivery toggle, and (for auction batches) a live descending price over WebSocket. |
| Store / Admin Dashboard | React + Tailwind, authenticated | Inventory view, batch status, manual override controls, Eco-Impact Analytics (dollars saved, lbs rescued, CO&#8322;e avoided). |
| NGO / Shelter Portal | React + Tailwind, authenticated | Standing Order rule management ("always prioritize dairy &amp; bread over 5kg, notify first for anything expiring within 6 hours"). |
| Map layer | Leaflet.js + OpenStreetMap tiles | Geofenced radius visualization. Mapbox GL JS is a documented upgrade path if richer styling is later needed. |

State management: keep it simple (React Context + hooks) unless the dashboard's complexity genuinely
outgrows it — do not introduce Redux/other state libraries without a `DECISIONS.md` entry justifying it.

---

## 3. Server-Side Architecture

| Component | Role |
|---|---|
| **FastAPI** | REST endpoints for inventory ingestion, claim creation, payment webhooks, standing-order CRUD; a WebSocket endpoint for the live auction price feed. |
| **Celery + Redis** | Celery beat runs the periodic expiry-risk scan and nightly model retraining; workers handle SMS/WhatsApp dispatch, OCR ingestion jobs, and delivery-fee calculation off the request/response path. Redis doubles as the Celery broker **and** the reservation-lock store (`reserved_until` TTL key per batch). |
| **PostgreSQL + PostGIS** | System of record for stores, batches, users, claims, standing orders. PostGIS powers the radius/distance queries behind geofenced targeting and delivery-fee logic. |
| **ML Inference** | Trained offline/nightly, loaded via Joblib inside a Celery task (or a small internal FastAPI route) so scoring a batch at scan time is a fast synchronous lookup, not a live training run. |
| **Twilio** | Outbound SMS/WhatsApp dispatch; inbound webhook receiver for "reply YES" claiming. |
| **Stripe / Razorpay** | Hosted checkout link generation; webhook receiver transitioning a reservation into a confirmed, paid claim. |

### 3.1 Request Flow

```
STORE INVENTORY (CSV / photo-OCR / manual entry)
        |
        v
 [FastAPI ingestion endpoint] --> PostgreSQL (batches table)
        |
        v
 [Celery beat: expiry-risk scan, every N minutes]
        |
        v
 [ML scorer]  <-- weather API, demand history, foot-traffic index
        |  (price, segment: B2C / B2B-NGO, urgency tier)
        v
 threshold breached? ----no----> re-check next scan
        | yes
        v
 [Celery worker: build geofenced audience via PostGIS radius query]
        |
        v
 [Twilio dispatch: SMS / WhatsApp]  --------->  end user's phone
        |                                            |
        |                                    taps link OR replies "YES"
        v                                            v
 [Redis: reserved_until TTL lock set]  <----  [FastAPI claim endpoint]
        |
        v
 [Stripe/Razorpay checkout link] --> user pays --> [webhook]
        |
        v
 [Claim CONFIRMED] --> pickup (QR code) or delivery (courier/volunteer queue)
        |
        v
 [Outcome logged: sold / expired / donated] --> feeds nightly retrain + impact dashboard
```

### 3.2 Data Model (core entities)

| Entity | Key fields |
|---|---|
| `Store` | id, name, geo-coordinates (PostGIS `POINT`), timezone |
| `Batch` | id, store_id, SKU, category, qty_on_hand, unit_cost, retail_price, current_price, received_date, expiry_date, status (`active/discounted/reserved/sold/expired/donated`) |
| `User` | id, phone (hashed/masked at rest where possible), coarse geo (opt-in), category opt-ins, reliability_score, channel_engagement_history |
| `Claim` | id, batch_id, user_id, reserved_until, status (`reserved/paid/expired/fulfilled`), fulfillment_type (`pickup/delivery`), payment_ref |
| `StandingOrder` | id, ngo_id, category_filter, min_quantity, priority_window_hours |
| `PriceEvent` | id, batch_id, price, triggered_by (`model/manual`), timestamp — the audit trail for every markdown decision |

### 3.3 API Design Conventions

- REST resources are plural nouns (`/batches`, `/claims`, `/standing-orders`); actions that don't map
  cleanly to CRUD use a verb sub-path (`/claims/{id}/confirm-payment`).
- All timestamps are UTC in storage and API responses; the frontend converts to store-local time for
  display.
- Every mutating endpoint that touches money or reservation state is idempotent with respect to
  webhook retries (Stripe/Razorpay and Twilio both retry on timeout).

---

## 4. Machine Learning Pipeline

### 4.1 Model A — Markdown / Price Optimization
Gradient-boosted regression (Scikit-Learn `GradientBoostingRegressor` / `HistGradientBoostingRegressor`
as the default; LightGBM/XGBoost as a documented swap-in if time allows) predicts expected sell-through
probability for a given discount depth, category, and context. A discrete search over candidate
discount levels (0%, 10%, ... 70%) then picks the level maximizing expected recovered revenue
(probability of sale × discounted price), subject to a hard floor that forces maximum discount once
hours-to-expiry drops below a critical threshold.

### 4.2 Model B — Segment / Channel Classifier
Logistic regression or a small decision tree decides B2C vs. B2B/NGO routing using batch size,
category, and historical B2B demand for that category.

### 4.3 Model C (stretch) — Predictive Pre-Alert
Classifier estimating probability that a discount triggers within the next N hours, powering the
"heads-up" pre-alert. Feature-engineered gradient boosting is sufficient; no true time-series model
(e.g. Prophet) is required for the current scope.

### 4.4 Cold Start
New stores/SKUs without sufficient history fall back to a category-level average shelf-life/elasticity
lookup table. This fallback must be visible in the dashboard (labeled as such), not silent.

### 4.5 Feature List (Model A)

`time_to_expiry_hours`, `category`, `current_price`, `cost_price`, `qty_on_hand`,
`avg_daily_velocity_7d`, `avg_daily_velocity_28d`, `temperature_today`, `precip_probability`,
`is_weekend`, `is_holiday`, `hour_of_day`, `store_foot_traffic_index`, `past_discount_depth`,
`past_sellthrough_rate`, `local_demand_score`, `b2b_flag`.

### 4.6 Training Methodology
- **Time-based train/test split** (train on earlier weeks, validate on most recent) — never a random
  split, to avoid leaking future information given the time-series nature of retail demand.
- Training data is currently **synthetic**, generated from realistic per-category price-elasticity
  curves plus noise, seeded for reproducibility. This must stay clearly labeled in code and docs until
  real retailer data is available — see `DECISIONS.md` for the entry documenting this choice.
- Nightly retraining via Celery beat once sufficient data accumulates; rule-based fallback (§4.4)
  activates automatically when model confidence or data volume for a SKU/category is too low.

---

## 5. External Integrations

| Integration | Purpose | Notes |
|---|---|---|
| OpenWeatherMap / Tomorrow.io | Weather feature input | Free tier sufficient for current scope |
| OpenStreetMap Nominatim | Geocoding | Free, used only if raw coordinates aren't already captured |
| Twilio | SMS + WhatsApp Business API | Sandbox mode acceptable pre-launch |
| Stripe / Razorpay | Payments | Test mode for all non-production environments |
| Tesseract (local OCR) | Shelf-label ingestion | No external API dependency/rate limit |

## 6. Non-Functional Notes

- **Idempotency:** every webhook handler (Twilio inbound, Stripe/Razorpay) must tolerate duplicate
  delivery without double-charging, double-reserving, or double-notifying.
- **Concurrency safety:** the Redis TTL lock on `reserved_until` is the single source of truth for
  "is this batch currently claimable" — do not add a second, competing locking mechanism.
- **Privacy boundaries:** see `SECURITY.md` for what user/location data is and isn't stored, and how
  payment data is scoped entirely to the processor.

---

*This document should be updated whenever an architectural decision changes what's described here.
Log the change itself in `DECISIONS.md`; update this file to reflect the new current state.*
