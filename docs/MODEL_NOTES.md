# OptiMart Model A — Pricing Model Notes

> **Audience:** Hackathon judges, investors, technical reviewers.  
> **Purpose:** Plain-English explanation of how the ML pricing engine works and why it was built this way.

---

## The Core Problem We Solved

Most food-waste reduction systems answer the question "how much should we discount this item?" with a simple rule: *items near expiry get a bigger discount.* That sounds obvious — but it fails immediately in the real world because **time-to-expiry has no absolute meaning without category context.**

| Product | Days Left | Urgency |
|---|---|---|
| Fresh Milk | 2 days | Near-crisis — discount 60–90% immediately |
| Packaged Biscuits | 2 days | Still well within shelf life, no discount needed |
| Cooking Oil | 2 days | Barely registered — literally irrelevant |

Feeding raw `days_to_expiry` into a pricing model trains it to believe that 2 days is always an emergency. It isn't. The model learns a completely wrong signal.

**OptiMart's solution: category-relative urgency normalization.**

---

## The Urgency Score

Before anything reaches the pricing model, we compute a single normalized signal called `urgency_score` (0 to 1):

```
urgency_score = f(days_to_expiry / category_typical_shelf_life)
```

Where `f()` is **not** always a straight line. We use two different urgency curves, chosen per category:

### Curve Type 1: Linear-Convex (Perishables)

Used for: **Dairy, Bakery, Meat & Seafood, Fruits & Veggies, Ready-to-Eat.**

Urgency rises from ~0 at purchase and accelerates toward expiry. The slight convex shape reflects how spoilage risk compounds daily — a milk carton doesn't go from "fine" to "bad" linearly; the last 24 hours carry disproportionately more risk.

```
urgency = (1 - days_remaining/shelf_life) ^ power
```

A `power` of 1.3–1.5 creates the convex acceleration. This means a dairy item loses its first few % of urgency very slowly, then the final 20% of shelf life accounts for 40%+ of urgency gain.

### Curve Type 2: Sigmoid Ramp (Long-Shelf Items)

Used for: **Perfume, Food Grains, Oil & Masala, Frozen, Snacks, Beverages.**

Urgency stays near **zero** for most of the product's life, then rises sharply only in the final 5–10% of shelf life. A perfume with 900 days of shelf life carries essentially no pricing pressure at 300 days, 200 days, even 60 days remaining — the urgency spike only becomes meaningful in the final ~45 days (5% of 900 days).

```
urgency = sigmoid(steepness × (fraction_elapsed - inflection_point))
```

The inflection point is set to 90–95% consumed, meaning urgency goes from ~0.05 to ~0.95 in a sharp window. This prevents the model from applying spurious discounts to slow-moving goods with plenty of life left.

---

## Why This Matters for the Model

By feeding `urgency_score` instead of raw `days_to_expiry`, the pricing model:

1. **Learns a universal signal** — 0.90 urgency means "near crisis" regardless of whether it's dairy or cooking oil.
2. **Doesn't need to re-learn category shelf-life baselines from scratch** — they're encoded in the feature engineering layer.
3. **Generalises to new categories** — adding "Fermented Drinks" or "Fresh Pasta" only requires updating `category_shelf_life.json`, not retraining.

---

## The Discount Selection Formula

The model does **not** directly output a discount percentage. Instead:

1. The model predicts **probability of sale** at a given price.
2. We search over discrete candidate discounts `[0%, 10%, 20%, ..., 70%]`.
3. For each candidate: `expected_revenue = sell_probability × candidate_price`.
4. We pick the discount that **maximises expected revenue**, not just sell-through.

This matters because maximising sell-through alone would always suggest 70% off. We want the discount that recovers the most rupee value — sometimes 10% off sells just as well as 30% off, so 10% is the right choice.

### Hard Constraints (in priority order)

| Priority | Constraint | Reasoning |
|---|---|---|
| 1 | `urgency_score > 0.90` → force max allowed discount | At this point, sell-through beats margin. Waste prevention is the goal. |
| 2 | `candidate_price < cost_price` → skip unless `force_liquidate=True` | Prevent selling below procurement cost except for terminal batches. |
| 3 | `discount ≤ category_markdown_ceiling` | Prevents commoditising premium products (e.g. never 70% off perfume). |

---

## Weather and Demand Context

The model incorporates weather through engineered **interaction features**:

- `cat_x_temp` = `weather_sensitivity × normalised_temperature`
- `cat_x_precip` = `weather_sensitivity × precipitation_probability`

Each category has a `weather_sensitivity` score (0 = zero weather effect, 0.9 = high effect):
- **Fruits & Veggies:** 0.9 — fresh produce demand spikes in heat, rain can suppress shopping trips.
- **Beverages:** 0.6 — cold drinks sell faster on hot days.
- **Perfume:** 0.0 — completely insensitive to weather.

By encoding this as explicit interaction features, the model doesn't have to discover from the data that "perfume doesn't care about rain." This is especially important given our limited training data volume.

---

## Training Data

> **!! All current training data is synthetic !!**  
> Generated by `synthetic_data.py` using hand-crafted statistical distributions.  
> Does NOT represent real retailer sales, real inventory, or real customer behaviour.  
> This is clearly flagged in the dataset via `df.attrs["SYNTHETIC_DATA"] = True`.

The synthetic data is structured to closely mirror what real data would look like:
- Per-category shelf-life distributions matching our lookup table.
- Realistic Indian subcontinent temperature/weather distributions.
- NegativeBinomial inventory quantities (most batches small, rare large ones).
- Per-category price elasticity curves with Gaussian noise.

When real retailer data is available, only `synthetic_data.py` needs to be replaced. The model interface (`predict()`, `recommend_discount()`) stays identical.

---

## Cold Start

For unknown categories or SKUs with no history, we fall back to a category-level heuristic based on the shelf-life lookup table's elasticity estimates. The result is always flagged with `reasoning_tags: ["cold_start_fallback"]` so the dashboard can show users that this is an estimated recommendation, not a model-driven one.

---

## Files

| File | Purpose |
|---|---|
| `category_shelf_life.json` | Per-category shelf-life baselines, curve parameters, markdown ceilings |
| `urgency.py` | `compute_urgency()` — the category-relative normalization layer |
| `synthetic_data.py` | Reproducible synthetic dataset generator |
| `train_model.py` | Training script (HistGradientBoostingRegressor + LinearRegression baseline) |
| `price_engine.py` | Discrete discount search, hard constraints, reasoning_tags output |
| `evaluate.py` | MAE/RMSE report on held-out time window |
| `predictor.py` | FastAPI-compatible singleton wrapper |

---

*OptiMart — AI Food-Waste Rescue Platform | Model A Documentation*
