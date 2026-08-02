# OptiMart

**Hyper-local food waste rescue platform — AI-driven dynamic markdown and real-time redistribution.**

OptiMart integrates with grocery inventories to continuously evaluate batch expiration timelines
against real-time variables (weather, historical demand, foot traffic). Instead of static, calendar-based
discounts, a machine learning engine computes the optimal markdown to liquidate stock efficiently. When
a batch crosses a critical expiry threshold, the platform automatically triggers targeted B2B/B2C flash
sales via SMS and WhatsApp to nearby buyers and shelters — turning potential retail loss into community
resources before spoilage occurs.

> For the full problem/market/ML/roadmap writeup this repo is built from, see the project playbook
> (`OptiMart_Hackathon_Playbook.pdf`, shared alongside this repo).

---

## Table of Contents

- [Core Features](#core-features)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Documentation Map](#documentation-map)
- [Project Status](#project-status)
- [License](#license)

---

## Core Features

| # | Feature | Summary |
|---|---------|---------|
| 1 | Predictive AI Markdown Engine | Scikit-Learn model factors weather, inventory volume, and time-to-expiry to set optimal discount depth. |
| 2 | Hyper-Local Geo-Fenced Targeting | PostgreSQL + PostGIS radius queries so alerts only reach realistically reachable users. |
| 3 | Frictionless Click-to-Claim | Tokenized, single-use claim link — no account, no app install. |
| 4 | Secure Checkout &amp; Fulfillment Choice | Reserve-then-pay flow (Stripe/Razorpay), pickup or delivery. |
| 5 | High-Concurrency Reservation Locking | Redis TTL locks prevent double-claiming on simultaneous alerts. |
| 6 | Eco-Impact Analytics Dashboard | Real-time dollars saved, lbs rescued, CO&#8322;e avoided. |
| 7 | Reliability Scoring | Claim-to-pickup ratio routes urgent alerts to dependable users first. |
| 8 | Rescue Squads (Standing Orders) | Shelters/NGOs subscribe to rule-based priority routing instead of one-off blasts. |
| 9 | Dynamic Descending-Price Auctions | Live WebSocket-driven price ticks for high-volume batches. |
| 10 | Shareable Impact Receipts | Auto-generated "you just rescued X lbs / saved Y kg CO2" social shareable. |
| 11 | WhatsApp + SMS Reply-to-Claim | Twilio-powered, works on low-connectivity/feature phones. |
| 12 | Zero-Effort Store Onboarding | OCR/barcode scan pre-fills batch expiry and product data. |
| 13 | Accessibility-First Claim Page | Low-bandwidth, large tap targets, multi-language toggle. |
| 14 | Predictive Pre-Alerts | "Likely to discount around 6 PM" heads-up notifications. |

## Tech Stack

- **Backend &amp; AI:** Python (FastAPI), Scikit-Learn, Joblib
- **Data &amp; Infra:** PostgreSQL + PostGIS, Redis, Celery
- **Frontend &amp; Mapping:** React.js, Tailwind CSS, Leaflet.js (Mapbox GL JS as upgrade path)
- **Communications:** Twilio API (SMS + WhatsApp Business API, inbound webhooks)
- **Payments:** Stripe / Razorpay (checkout + webhooks)

Full rationale for each choice lives in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Repository Structure

```
optimart/
├── backend/
│   ├── app/                # FastAPI application
│   │   ├── api/             # route modules (inventory, claims, payments, standing-orders)
│   │   ├── ml/               # model training scripts, joblib artifacts, feature pipeline
│   │   ├── tasks/            # Celery tasks (scan, dispatch, retrain, OCR ingestion)
│   │   ├── models/           # SQLAlchemy models
│   │   └── core/              # config, security, db session
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/claim/       # public claim page
│   │   ├── pages/dashboard/   # store admin dashboard
│   │   ├── pages/ngo/         # standing-order portal
│   │   └── components/
├── infra/
│   ├── docker-compose.yml
│   └── .env.example
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RULES.md
│   ├── AGENT.md
│   ├── CONTRIBUTING.md
│   ├── SECURITY.md
│   ├── STATUS.md
│   └── DECISIONS.md
└── README.md
```

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> optimart && cd optimart
cp infra/.env.example infra/.env   # fill in Twilio / Stripe-Razorpay / weather API keys

# 2. Boot the stack
docker compose -f infra/docker-compose.yml up --build

# 3. Seed demo data (stores, batches, users) for a working demo out of the box
docker compose exec backend python -m app.scripts.seed_demo_data

# 4. Open
# Claim page (public):     http://localhost:3000
# Store dashboard:         http://localhost:3000/dashboard
# API docs (FastAPI):      http://localhost:8000/docs
```

## Documentation Map

| File | Purpose |
|------|---------|
| [`RULES.md`](./RULES.md) | How work happens here — phase discipline, branching, commits, permission gates. |
| [`AGENT.md`](./AGENT.md) | Onboarding for AI coding agents (Claude Code and others) working in this repo. |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Client/server architecture, data flow, ML pipeline, schema overview. |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | How human contributors set up, branch, and submit changes. |
| [`SECURITY.md`](./SECURITY.md) | Data handling, secrets, PCI/PII boundaries, responsible disclosure. |
| [`STATUS.md`](./STATUS.md) | Live snapshot of what's built, in progress, and blocked. |
| [`DECISIONS.md`](./DECISIONS.md) | Append-only log of technical decisions and their rationale. |

## Project Status

See [`STATUS.md`](./STATUS.md) for the current phase and what's built. As of repo creation, the
project is at **Phase 0 — Setup**.

## License

TBD — no license has been chosen yet. Do not treat this code as open for reuse until a `LICENSE`
file is added. See the note in `CONTRIBUTING.md`.
