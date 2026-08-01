# NEXPIRE — Extended Demo Script (Ch. 14.1)
**Phase 13 deliverable | ~5–5.5 minutes total**

---

## The One-Sentence Opener

> *"InvenSight predicts what to order, watches what's at risk, and rescues what would otherwise be lost — one system, one data flow."*

Open on the **loop diagram** (the closed-loop architecture diagram in the dashboard or slide). Hold it for 15 seconds. Let it read. Do not click anything yet.

---

## Run-of-Show

### ⏱ 0:00–0:30 — The Loop Diagram

**Action:** Display the closed-loop architecture.

**Narration:**
> "Before I show you any numbers, I want you to see the structure. InvenSight is two models that talk to each other. On the left: **Model D** — it reads our sales history and forecasts demand seven days forward per SKU. On the right: **Model A** — it watches expiry risk and sets optimal markdown prices. The connection between them is the point: when Model D flags that a SKU is selling slower than forecast, Model A automatically triggers an earlier, deeper discount. That's the loop. Everything you're about to see is one system."

---

### ⏱ 0:30–1:00 — Demand & Reorder Tab

**Action:** Click the **"Demand & Reorder"** tab in the dashboard.

1. Select a store from the dropdown (e.g., **Fresh Mart Mumbai**).
2. Click **"Run Forecast"**.
3. Click a SKU row in the recommendation table — the **forecast-vs-actual trend chart** renders.

**Narration:**
> "This is the Demand & Reorder tab. Model D has just run for this store. Here's the forecast-vs-actual chart for *[SKU name]*. The dark line is what we actually sold over the past 28 days. The green line is the naive baseline — a simple rolling average. The orange band is Model D's quantile regression — it's giving us a median forecast with confidence bounds."

4. Point to the "Why" factors panel below the chart.

**Narration:**
> "Below the chart: the model tells the retailer *why* it made this recommendation. In this case: upcoming weekend demand spike and low stockout rate. The retailer can accept, adjust, or dismiss — and that decision feeds back into future training."

5. Click **"✓ Accept"** on the recommendation.

---

### ⏱ 1:00–1:15 — The Connective-Tissue Beat *(most important 15 seconds)*

**Action:** Switch to the **"Inventory"** tab.

1. Find a batch row where the SKU is known to be underperforming its forecast (e.g., **DAI-1029** or **FRU-9402** — items with 1–2 days left and high category risk).
2. Click **"⚡ Reprice"** on that row.
3. A **warning toast** appears: *"⚠️ Underperforming sales vs forecast, applied +25% risk boost!"*

**Narration:**
> "Here's the connective tissue. This SKU — *[name]* — has been selling at only 30% of its Model D forecast for the past seven days. When I hit Reprice, Model A doesn't just look at expiry. It checks the forecast. It sees the underperformance. It automatically escalates the risk score and triggers a deeper markdown — *before* the expiry deadline forces our hand. The loop is not just a diagram. It's running right now."

---

### ⏱ 1:15 onward — Hand off to Volume I run-of-show

*(Continue from Volume I Ch. 15.1, step 0:30 mark)*

**Action:** Stay on the **Inventory** tab.

4. Select a dairy batch with 2 days to expiry — point to the current price and discount badge.
5. Switch to the **"ML Dynamic Discounting"** tab.

**Narration:**
> "Now watch what happens at the batch level. I'll use the discount predictor for this dairy batch — 2 days to expiry, 45 units, ₹75 original price."

6. Fill in the simulation form and click **"Calculate Optimal ML Discount"**.
7. Show the result: risk level, optimal price, consumer savings, and the **"System Signals & Logic"** badge strip.

---

### ⏱ ~2:30 — SMS Alert & Claim Flow

**Action:** Navigate to the **"Notifications"** tab.

8. Dispatch a notification for the dairy batch — show the WhatsApp/SMS template.
9. Open the **claim page** (`/claim/[token]`) in a second browser tab.

**Narration:**
> "The consumer receives a hyper-local alert. They tap the link. This is the claim page — no app download, no account. One tap. The batch is reserved in Redis with a 15-minute TTL. Payment goes through Razorpay — India's primary gateway — directly here."

---

### ⏱ ~3:30 — NGO Queue & Eco-Impact Close

**Action:** Navigate to the **"Standing Orders"** tab.

10. Show an NGO standing order (category: Dairy, subsidized: true).
11. Run the evaluation — show the matched reservation.

**Action:** Navigate to the **"Analytics"** tab.

12. Show the Eco-Impact dashboard: kg food rescued, CO₂ offset, revenue recovered.

**Narration:**
> "Every rescued batch hits this dashboard. For the retailers: revenue they'd have written off. For the NGOs: food, delivered, zero friction. For the city: measurable CO₂ offset from landfill avoidance. One system drives all three numbers."

---

## Closing Line

> *"The idea — reducing food waste by connecting expiration tracking to real inventory decisions — is something we'd been thinking about before today. But this problem statement is what actually pushed us to build the piece that made it work: demand forecasting. Almost everything you're seeing — the model, the forecasting logic, the connection between ordering and markdown — was built in the last 24 hours, and we can walk through exactly what and where in our sources log if you're curious."*

---

## Backup Recording Plan

- **Before the demo day:** Record a full 5.5-minute screen-capture walkthrough with narration using the seeded data.
- **Seeded state to lock in:** Ensure `docker exec nexpire-api python scripts/seed.py` re-creates reproducible store/batch/sales data before recording.
- **Fallback trigger:** If live demo fails (network, Docker, DB), switch to the recording immediately. Do not attempt a re-run mid-presentation.
- **File storage:** Keep the recording in two locations (local + cloud) before the event.
