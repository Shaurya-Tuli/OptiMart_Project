# 📋 OptiMart — Updated Project Write-Up

## The 60-Second Elevator Pitch

> "Every single day, grocery stores, distribution centers, and restaurants throw away millions of tons of perfectly good food simply because it is approaching an expiration date or weather changes drop foot traffic.
> **OptiMart** solves this by converting potential financial losses and environmental waste into an automated, real-time marketplace. It uses an embedded machine learning engine to monitor store inventories, predict how fast food will spoil based on external variables like weather, dynamically slash prices to an optimized point, and automatically broadcast instant SMS and WhatsApp flash sales to local buyers and shelters within a geo-fenced radius. Users pay securely through the claim link and choose to pick the item up themselves or have it delivered — while shelters and NGOs receive it free, subsidized by consumer payments. We don't just track waste; we eliminate it programmatically, sustainably, and as frictionlessly as replying 'YES' to a text."

---

## 🛠️ How It Works (The Core System)

1. **Monitor:** It scans the store's database constantly for batches nearing expiration.
2. **Predict:** The **Machine Learning Engine** evaluates *why* an item isn't selling (weather, foot traffic patterns, time of day) and also generates early forecasts of when a discount is likely to trigger.
3. **Price:** The AI calculates the exact discount needed to move inventory — either as a fixed markdown or, for high-volume batches, a live descending-price window.
4. **Alert:** The system triggers hyper-local **SMS and WhatsApp broadcasts via Twilio**, with soft "heads-up" pre-alerts sent earlier to interested users.
5. **Reserve:** Tapping the claim link puts a short-lived hold on the item (row-locked with a `reserved_until` timestamp) while the user completes checkout.
6. **Pay & Choose Fulfillment:** The user pays securely (Stripe/Razorpay) and selects **self-pickup** or **delivery**. Shelters/NGOs on Standing Orders skip payment entirely — their claims are subsidized.
7. **Fulfill:** Pickup users get a QR code for in-store collection; delivery users get a tracked delivery request routed to a courier/volunteer network.
8. **Reflect:** After fulfillment, the system generates a shareable "impact receipt" and updates the user's reliability score for future prioritization.

---

## ✨ Core Features

### 1. The Predictive AI Markdown Engine
A Scikit-Learn model looks beyond the clock — factoring in weather, inventory volume, and time-to-expiry to set an optimal discount, and to decide whether to target consumers or B2B bulk buyers (like shelters or commercial kitchens) who are less weather-sensitive.

### 2. Hyper-Local Geo-Fenced Targeting
PostgreSQL + PostGIS powers tight radius calculations (5–10 min walk/drive) so alerts only reach people close enough to realistically make the pickup window.

### 3. Frictionless "Click-to-Claim" Interface
A tokenized, single-use link opens a lightweight web page — no account, no app install — with a QR code generated on confirmation.

### 3a. Secure Checkout & Fulfillment Choice
Clicking the claim link places a short-lived reservation on the item, then walks the user through a quick, secure payment step (Stripe/Razorpay). After payment, the user chooses **self-pickup** (QR code, discounted price) or **delivery** (tracked, discounted price + delivery fee). Shelters and NGOs on Standing Orders bypass payment entirely — their claims are subsidized by consumer payments, turning the payment layer into a sustainability model rather than pure monetization.

### 4. High-Concurrency Transaction Security
Database-level row locking prevents double-claiming when many users receive the same limited-quantity alert simultaneously.

### 5. Automated Eco-Impact Analytics Dashboard
A React dashboard visualizing dollars saved, pounds of food rescued, and CO₂ emissions prevented in real time.

---

## 🌟 New Unique Differentiators

### 6. Reputation & Reliability Scoring
Every user builds a pickup-reliability score based on their claim-to-pickup ratio. Time-sensitive, short-expiry alerts are routed first to users with strong reliability history — directly reducing the "claimed but never picked up" failure mode that plagues most food-rescue apps.

### 7. "Rescue Squads" — Standing Orders for Shelters/NGOs
Shelters and NGOs can set standing preferences (e.g., "always prioritize us for dairy and bread over 5kg, notify first for anything expiring within 6 hours") instead of relying on one-off blasts. This exposes the existing B2B-targeting logic in the ML model as a subscribable rule set, reinforcing the "eliminate waste, don't just track it" pitch.

### 8. Dynamic Multi-Tier Auctions (Descending Price)
For high-volume batches, price ticks down live on the claim page every few minutes until someone claims it — a small real-time state machine (WebSocket or polling-driven) that's both technically interesting and visually compelling in a demo.

### 9. Shareable Impact Receipts
After every claim, a templated image ("You just rescued 4.2 lbs of food and saved 6.1 kg CO₂") is generated for users to share on social media — turning the analytics dashboard's data into a lightweight viral/marketing loop.

---

## 🚀 New Accessibility & Ease-of-Use Features

### 10. WhatsApp Integration Alongside SMS
Using the same Twilio integration already in place (via the WhatsApp Business API), alerts can include richer content — food photos, map previews, tappable buttons — with typically higher engagement than plain SMS, especially in regions like India.

### 11. One-Tap Claim via SMS Reply
Users with poor connectivity or those who prefer not to open a link can simply reply "YES" (or a keyword) directly to the SMS to claim an item, handled via Twilio's inbound SMS webhooks — removing an entire step of friction.

### 12. Store-Side "Zero Effort" Onboarding
Store staff can snap a photo of a shelf label or scan a barcode, with OCR/barcode recognition pre-filling the batch's expiry and product details — removing the biggest real-world adoption barrier: manual data entry.

### 13. Accessibility-First Claim Page
Large tap targets, low-bandwidth optimization (functions well on 2G), and multi-language toggle support — designed with the actual end users in mind, including shelters and lower-income claimers who may not have high-end devices or fast connections.

### 14. Predictive Pre-Alerts
Using the same ML model's forecasting capability, the system sends an earlier "heads-up" notification (e.g., "Milk likely to be discounted around 6 PM tonight") before the discount actually triggers, letting users plan ahead rather than only react in the moment.

---

## 💳 Payment & Delivery Layer

### 15. Reserve-Then-Pay Locking
When a user taps a claim link, the item is held with a short `reserved_until` window (e.g., 3 minutes) rather than being locked permanently on click. If payment isn't completed in that window, the hold releases and the item becomes claimable again — extending the existing high-concurrency lock system rather than replacing it.

### 16. Integrated Checkout (Stripe / Razorpay)
A server-generated checkout link handles payment; a webhook confirms success and transitions the reservation into a confirmed claim. Razorpay is the natural fit if the deployment is India-facing, pairing well with the existing Twilio/WhatsApp integration.

### 17. Pickup vs. Delivery Toggle
After payment, users choose:
- **Self-pickup** — discounted price only, generates the existing QR-code claim token.
- **Delivery** — discounted price plus a distance-based fee (reusing the PostGIS radius logic already built for geo-fencing), routed to a courier or volunteer driver network, with status tracked on the claim page (pending → out for delivery → delivered).

### 18. Subsidized Free Access for Shelters/NGOs
Standing Orders accounts (shelters, NGOs) are flagged to skip payment entirely — their claims stay free or heavily subsidized. This keeps the social-impact core of the project intact while consumer payments fund operations, effectively a pay-it-forward model: general public payments subsidize free rescue for shelters.

### 19. Revenue Split Logic
Payments are split automatically between the store (majority share) and the platform (small service fee), with delivery fees routed separately to cover courier/driver costs — giving the project an actual sustainable business model rather than relying on grants or donations.

---

## 🎯 Technical Stack

* **Backend & AI:** Python (FastAPI), Scikit-Learn, Joblib
* **Data & Infrastructure:** PostgreSQL (with PostGIS), Redis, Celery
* **Frontend & Mapping:** React.js, Tailwind CSS, Mapbox GL JS
* **Communications:** Twilio API (SMS + WhatsApp Business API, inbound webhook handling)
* **New additions:** OCR/barcode recognition for store onboarding, WebSocket layer for live descending-price auctions, lightweight image-generation service for shareable impact receipts
* **Payments & Delivery:** Stripe or Razorpay (checkout + webhooks), courier/delivery-partner API or a lightweight volunteer-driver queue, extended PostGIS logic for delivery fee calculation

---

## 🧭 Notes for Pitching

- **Reliability scoring** and **standing orders for NGOs** are strong answers if judges ask "how do you prevent no-shows or wasted alerts?"
- The **descending-price auction** is your best live-demo moment — it's visual, real-time, and clearly differentiated from a static discount.
- **WhatsApp + SMS-reply claiming** directly answers "how do you make this usable for people without smartphones or reliable data?" — a common judge question for social-impact projects.
- **Accessibility-first design** is worth mentioning proactively (rather than waiting to be asked) since it shows you thought about your actual end users, not just the tech.
- The **payment + delivery layer** is your strongest answer to "how does this actually sustain itself?" — frame it as pay-it-forward: consumer payments fund free access for shelters, plus a small platform fee makes the project viable beyond a hackathon demo.
- If asked about the reserve-then-pay lock, be ready to explain the timeout window and what happens on expiry — judges like probing edge cases like "what if payment fails halfway through?"
