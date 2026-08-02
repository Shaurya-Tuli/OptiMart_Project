# OptiMart — Judge Q&A Preparation (Ch. 14.2)
**Phase 13 deliverable — rehearse these answers confidently, not defensively**

---

## Q1 — The Most Likely Tough Question

> **"How do you validate a forecast when you can't wait a week during a demo?"**

**Rehearsed Answer (Ch. 12.5 honest framing):**

> "Great question — and it's the right one to ask. We can't wait a week. The pipeline is real and the mechanism is real; the specific numbers you're seeing are demonstrating the mechanism, not making a production-accuracy claim.
>
> What we can show you right now: the model's forecast-vs-actual chart uses 28 days of seeded historical data, and we benchmark it against a naive 7-day rolling average. The gradient-boosted quantile model beats that baseline on our seeded dataset — you can see the numbers on the chart. For a production deployment, you'd validate on held-out weeks of real POS data.
>
> The more important point is the structural claim: when the forecast says a SKU should sell 100 units and it's sold 28, something is wrong. The model doesn't need to be perfect to know that. That's the signal that triggers the earlier markdown — and that signal works regardless of whether our exact numbers are right."

**Key phrases to practice:**
- *"The pipeline is real and swappable"* — not *"the numbers are perfect"*
- *"Demonstrating the mechanism, not making a production-accuracy claim"*
- *"We benchmark against a naive baseline — you can see it on the chart"*

---

## Q2 — "You're using synthetic data — isn't that just making things up?"

**Rehearsed Answer:**

> "The training data is synthetic, yes — generated with realistic per-category seasonality, day-of-week patterns, promotional spikes, and stockout noise. We're transparent about that: it's documented in SOURCES.md and DECISIONS.md.
>
> The reason is practical: we can't use a real retailer's POS data in a hackathon. But the model architecture is the same you'd use with real data — HistGradientBoostingRegressor with quantile loss, the same features (lags, day-of-week, promo flags). Swapping in real POS data is a data connection, not a model rebuild. The pipeline is production-ready in structure."

---

## Q3 — "Is this really a closed loop, or just two features duct-taped together?"

**Rehearsed Answer:**

> "It's a genuine closed loop — and I can show you right now, not just narrate it. When I click Reprice on a batch whose SKU has underperformed its forecast, Model A's risk score gets a quantified boost — 0.25 points, capped at 1.0 — and you see a deeper markdown. The signal travels: sales history → demand forecast → pricing engine → earlier markdown. The test suite verifies it: `test_loop_integration.py` seeds an underperforming scenario and asserts the reasoning tag fires. It's testable, not just narrated."

---

## Q4 — "How is this different from just using expiry-based discounting?"

**Rehearsed Answer:**

> "Expiry-based discounting reacts to time. OptiMart reacts to *demand signals* before time runs out. A product with 5 days left and strong sales doesn't need a markdown — Model A keeps the price high. A product with 5 days left and 70% fewer sales than forecast gets flagged *now*, not on day 4. The forecast is what separates proactive from reactive — and it's what a pure expiry-based system structurally cannot do."

---

## Q5 — "What's the business model?"

*(Unchanged from Volume I — include for completeness)*

> "Retail SaaS subscription per store, tiered by inventory volume. NGO partnerships are subsidized or cost-price — food rescue is the social impact hook, not the revenue model. The revenue model is the retailer reducing waste and recovering margin they'd otherwise write off."

---

## Q6 — "What about data privacy / POS data agreements?"

> "In production, we'd use a retailer's own POS data under a standard data processing agreement — similar to how any inventory management SaaS works. The model runs in the retailer's cloud or on-premise; we never need to hold their raw sales data. For the hackathon, we generated synthetic data under a documented seed for reproducibility."

---

## Pre-Demo Checklist

- [ ] Docker containers healthy: `docker ps` shows `optimart-api` and `optimart-db` running
- [ ] Seed data loaded: `docker exec optimart-api python scripts/seed.py`
- [ ] Sales history generated: `docker exec optimart-api python scripts/generate_sales_history.py`
- [ ] At least one ReorderRecommendation seeded per store: `POST /api/v1/forecast/generate/{store_id}`
- [ ] Dashboard accessible at `http://localhost:3000`
- [ ] API docs accessible at `http://localhost:8000/docs`
- [ ] Backup recording saved locally and to cloud storage
- [ ] SOURCES.md and DECISIONS.md final pass complete
- [ ] Know which specific SKU / batch you'll use for the connective-tissue beat (1:00–1:15)
