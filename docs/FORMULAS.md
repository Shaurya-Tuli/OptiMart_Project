# OptiMart AI Pricing & Markdown Engine Formulas

This document lists the primary mathematical formulas and logic used by the machine learning dynamic discounting engine in OptiMart.

---

## 1. Perishability Index ($P$)
Each product category is assigned a weight based on its baseline decay/spoilage rate:
*   **Meat & Seafood:** $1.5$
*   **Fruits & Veggies:** $1.4$
*   **Ready-to-Eat:** $1.4$
*   **Dairy:** $1.3$
*   **Bakery:** $1.2$
*   **Beverages:** $0.8$
*   **Snacks:** $0.7$
*   **Oil & Masala:** $0.5$
*   **Food Grains:** $0.4$

---

## 2. Spoilage Decay ($F_{decay}$)
An exponential decay curve over the time-to-expiry timeline, scaled by the perishability coefficient ($P$):
$$F_{decay} = e^{-0.25 \times \frac{\text{DaysToExpiry}}{P}}$$

---

## 3. Ambient Temperature Impact ($F_{temp}$)
Higher temperature levels accelerate spoilage rates for fresh foods:
$$F_{temp} = 1.0 + \max\left(0, (\text{Temperature}_{C} - 25.0) \times 0.02\right)$$

---

## 4. Quantity Waste Risk ($F_{qty}$)
Higher stock quantities nearing expiry are scaled up to prompt higher clearance rate urgency:
$$F_{qty} = 1.0 + \min\left(0.5, \frac{\text{Quantity}}{100} \times 0.2\right)$$

---

## 5. Product Physical Condition Multiplier ($C$)
Visual or physical quality checks scale the baseline decay rate:
*   **Perfect / Excellent:** $1.0\times$
*   **Good / Light Bruising:** $1.15\times$
*   **Fair / Moderate Wear:** $1.35\times$
*   **Near Expiration / Damaged Package:** $1.6\times$

---

## 6. Combined Spoilage Risk Score ($R_{raw}$)
Combines all factors with normal noise parameter ($\mathcal{N}(0, 0.03)$) representing real-world stochasticity, clipped between 5% and 99%:
$$\text{Risk Score} = \text{clip}\left(F_{decay} \times F_{temp} \times F_{qty} \times C + \mathcal{N}(0, 0.03),\, 0.05,\, 0.99\right)$$

---

## 7. Discount & Suggested Pricing
The predicted waste risk score is mapped directly to a discount percentage range:
*   **Low Risk ($R < 0.20$):** $0\% - 10\%$ discount
*   **Medium Risk ($0.20 \le R < 0.45$):** $15\% - 30\%$ discount
*   **High Risk ($0.45 \le R < 0.75$):** $35\% - 60\%$ discount
*   **Critical Risk ($R \ge 0.75$):** $65\% - 90\%$ discount

The suggestion ensures cost margin protection:
$$\text{Suggested Price} = \text{Original Selling Price} \times \left(1.0 - \frac{\text{Discount}_{\%}}{100}\right)$$
