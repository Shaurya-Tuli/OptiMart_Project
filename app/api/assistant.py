"""
assistant.py — OptiMart AI Assistant API
=========================================
Provides a /api/v1/assistant/chat endpoint that powers the customer-facing
chatbot widget. It understands queries about:
  - Current discounts & sales
  - Product search by category / location
  - How to claim a product
  - General FAQ (expiry, payment, safety)
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.batch import Batch

router = APIRouter(prefix="/api/v1/assistant", tags=["AI Assistant"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    role: Optional[str] = "customer"     # "retailer" | "customer"
    history: Optional[List[ChatMessage]] = []
    store_id: Optional[int] = None


class ProductCard(BaseModel):
    id: int
    product_name: str
    category: str
    discount_percentage: float
    original_price: float
    current_price: float
    quantity: int
    expiration_date: str
    store_id: int
    claim_action: str   # deeplink hint for the frontend


class ChatResponse(BaseModel):
    reply: str
    intent: str                         # detected intent label
    products: List[ProductCard] = []    # inline product cards (if any)
    quick_replies: List[str] = []       # suggested follow-up chips


# ---------------------------------------------------------------------------
# Intent detection (lightweight rule-based — no external LLM dependency)
# ---------------------------------------------------------------------------
_GREET_PATTERNS = re.compile(
    r"(hi|hello|hey|hiya|namaste|good morning|good evening|howdy)", re.I
)
_DISCOUNT_PATTERNS = re.compile(
    r"(discount|sale|offer|deal|cheap|save|saving|markdown)", re.I
)
_CATEGORY_MAP = {
    "dairy":         "Dairy",
    "milk":          "Dairy",
    "paneer":        "Dairy",
    "yogurt":        "Dairy",
    "bakery":        "Bakery",
    "bread":         "Bakery",
    "cake":          "Bakery",
    "fruit":         "Fruits & Veggies",
    "vegetable":     "Fruits & Veggies",
    "veggie":        "Fruits & Veggies",
    "veg":           "Fruits & Veggies",
    "produce":       "Fruits & Veggies",
    "meat":          "Meat & Seafood",
    "chicken":       "Meat & Seafood",
    "fish":          "Meat & Seafood",
    "seafood":       "Meat & Seafood",
    "snack":         "Snacks",
    "chips":         "Snacks",
    "biscuit":       "Snacks",
    "frozen":        "Frozen",
    "ice cream":     "Frozen",
    "grain":         "Food Grains",
    "rice":          "Food Grains",
    "atta":          "Food Grains",
    "dal":           "Food Grains",
    "pulse":         "Food Grains",
    "beverage":      "Beverages",
    "juice":         "Beverages",
    "drink":         "Beverages",
    "oil":           "Oil & Masala",
    "masala":        "Oil & Masala",
    "spice":         "Oil & Masala",
    "ready":         "Ready-to-Eat",
    "meal":          "Ready-to-Eat",
    "prepared":      "Ready-to-Eat",
    "perfume":       "Perfume & Cosmetics",
    "cosmetic":      "Perfume & Cosmetics",
}
_CLAIM_PATTERNS = re.compile(
    r"(claim|reserve|buy|purchase|how to get|order|pickup|pick up|collect|how do i)", re.I
)
_EXPIRY_PATTERNS = re.compile(
    r"(expir|shelf life|safe|still good|fresh|spoil)", re.I
)
_PAYMENT_PATTERNS = re.compile(
    r"(pay|payment|upi|cash|card|subsidize|free|subsidy|ngo|price)", re.I
)
_HELP_PATTERNS = re.compile(
    r"(help|what can you do|what do you do|support|guide|how does|how do)", re.I
)


_RETAILER_FORECAST = re.compile(
    r"(forecast|model d|predict|p10|p90|confidence|future demand|seasonality|trend|horizon|curve)", re.I
)
_RETAILER_SALES = re.compile(
    r"(actual|sales|history|units sold|revenue|historical|past sales|daily sales|sold)", re.I
)
_RETAILER_REORDER = re.compile(
    r"(reorder|order quantity|safety stock|buffer|replenish|inventory on hand|qty on hand|stockout)", re.I
)
_RETAILER_NAV = re.compile(
    r"(navigate|go to|where is|how to navigate|tab|simulator|claims|notification|timeline|tab 1|tab 2|tab 3|tab 4|tab 5)", re.I
)


def _detect_intent(message: str, role: str = "customer") -> tuple[str, Optional[str]]:
    """Returns (intent, category_filter). Handles both Retailer and Customer roles."""
    msg_lower = message.lower()

    if role == "retailer":
        if _GREET_PATTERNS.search(msg_lower) or _HELP_PATTERNS.search(msg_lower):
            return "retailer_greeting", None
        if _RETAILER_FORECAST.search(msg_lower):
            return "retailer_forecast", None
        if _RETAILER_SALES.search(msg_lower):
            return "retailer_sales", None
        if _RETAILER_REORDER.search(msg_lower):
            return "retailer_reorder", None
        if _RETAILER_NAV.search(msg_lower):
            return "retailer_navigation", None
        return "retailer_greeting", None

    # Customer Role Intent Detection
    if _GREET_PATTERNS.search(msg_lower):
        return "greeting", None

    # Check category keywords first
    matched_category = None
    for kw, cat in _CATEGORY_MAP.items():
        if kw in msg_lower:
            matched_category = cat
            break

    if matched_category:
        return "search_category", matched_category

    if _CLAIM_PATTERNS.search(msg_lower):
        return "claim_guide", None

    if _EXPIRY_PATTERNS.search(msg_lower):
        return "expiry_faq", None

    if _PAYMENT_PATTERNS.search(msg_lower):
        return "payment_faq", None

    if _HELP_PATTERNS.search(msg_lower):
        return "help", None

    if _DISCOUNT_PATTERNS.search(msg_lower):
        return "browse_discounts", None

    return "browse_discounts", None  # default: show discounts


# ---------------------------------------------------------------------------
# Product fetching helpers
# ---------------------------------------------------------------------------
def _fetch_discounted_batches(
    db: Session,
    category: Optional[str] = None,
    store_id: Optional[int] = None,
    limit: int = 6,
) -> List[Batch]:
    q = db.query(Batch).filter(
        Batch.status.in_(["ACTIVE", "DISCOUNTED"]),
        Batch.discount_percentage > 0,
        Batch.expiration_date >= date.today(),
    )
    if category:
        q = q.filter(Batch.category.ilike(f"%{category}%"))
    if store_id:
        q = q.filter(Batch.store_id == store_id)
    return (
        q.order_by(Batch.discount_percentage.desc())
        .limit(limit)
        .all()
    )


def _batch_to_card(b: Batch) -> ProductCard:
    return ProductCard(
        id=b.id,
        product_name=b.product_name,
        category=b.category,
        discount_percentage=round(b.discount_percentage, 1),
        original_price=round(b.original_selling_price, 2),
        current_price=round(b.current_price, 2),
        quantity=b.quantity,
        expiration_date=str(b.expiration_date),
        store_id=b.store_id,
        claim_action=f"claim:{b.id}",
    )


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------
_QUICK_DEFAULTS = [
    "Show all discounts 🛒",
    "Dairy deals 🥛",
    "Bakery deals 🍞",
    "How do I claim? 🤝",
]


def _build_response(
    intent: str,
    category: Optional[str],
    products: List[Batch],
    message: str,
) -> ChatResponse:
    cards = [_batch_to_card(b) for b in products]
    n = len(cards)

    # Retailer Intents
    if intent == "retailer_greeting":
        reply = (
            "📊 **Welcome to OptiMart Retailer Copilot!**\n\n"
            "I'm here to help you analyze store performance, understand demand forecasts, and navigate the Retailer Portal.\n\n"
            "**What I can do for you:**\n"
            "• 🎯 **Demand Forecasting**: Model D 7-day demand predictions & p10-p90 confidence bands\n"
            "• 📈 **Actual Sales**: Analyze historical sales_history data across categories\n"
            "• 📦 **Reorder Recommendations**: Safety stock calculations & order quantity deltas\n"
            "• 🧭 **Portal Navigation**: Jump directly to any tab (Inventory, Forecasts, Simulator, Claims, Notifications)\n\n"
            "What would you like to explore?"
        )
        quick = ["🎯 Demand Forecasting", "📦 Reorder Quantities", "📈 Actual Sales", "🧭 Navigate Portal"]

    elif intent == "retailer_forecast":
        reply = (
            "🎯 **Demand Forecasting (Model D Intelligence):**\n\n"
            "• **Model D** predicts 7-day demand using gradient boosted quantile regression (p10, p50, p90).\n"
            "• **Seasonality Decomposition**: 7-day total demand is mapped to a daily curve based on historical day-of-week sales.\n"
            "• **Confidence Band (p10-p90)**: Band width reflects model uncertainty — wider spread = higher buffer scaling.\n"
            "• **Baseline Benchmark**: Model D outperforms the 7-day rolling average naive baseline.\n\n"
            "👉 Tap **🎯 Demand Forecasting** in the menu below to open Graph A, Graph B & Graph C!"
        )
        quick = ["🎯 Go to Demand Forecasting", "📦 Reorder Quantities", "📈 Actual Sales", "🧪 ML Discount Simulator"]

    elif intent == "retailer_sales":
        reply = (
            "📈 **Actual Sales & History Analytics:**\n\n"
            "Here is the latest 7-day completed sales total from `sales_history`:\n"
            "• 🥛 **Milk (Dairy)**: **198 units**\n"
            "• 🍞 **Bread (Bakery)**: **236 units**\n"
            "• 🍏 **Veggies & Fruits**: **190 units**\n"
            "• 🥩 **Meat & Seafood**: **149 units**\n"
            "• 🍿 **Snacks**: **137 units**\n"
            "• 🌾 **Food Grains**: **194 units**\n\n"
            "Actual demand values are automatically plotted on **Graph C** as green reference lines (`◆ Actual`) for buffer efficiency evaluation."
        )
        quick = ["🎯 Demand Forecasting", "📦 Reorder Quantities", "📊 Current Inventory Timeline", "🧭 Navigate Portal"]

    elif intent == "retailer_reorder":
        reply = (
            "📦 **Reorder Recommendations & Safety Stock:**\n\n"
            "• **Formula**: `Recommended Qty = max(0, Predicted Demand + Safety Stock − Current Qty On Hand)`\n"
            "• **Safety Buffer**: Scales inversely with confidence (`confidence = 1 - spread / pred_demand`). High uncertainty = bigger buffer.\n"
            "• **Business Impact (Graph C)**: Compares Model D's order recommendation vs. Naive Baseline to prevent over-stocking and waste.\n\n"
            "Need to adjust or accept recommendations? Check the Reorder Table in Tab 2!"
        )
        quick = ["🎯 Go to Demand Forecasting", "📈 Actual Sales", "⚡ Flash Claims"]

    elif intent == "retailer_navigation":
        reply = (
            "🧭 **Retailer Portal Navigation Guide:**\n\n"
            "1. 📊 **Current Inventory Timeline (Tab 1)**: Simulated stock flow & 7-day replenishment events.\n"
            "2. 🎯 **Demand Forecasting & Reorder (Tab 2)**: Graphs A, B & C + Reorder Recommendations Table.\n"
            "3. 🧪 **ML Discount Simulator (Tab 3)**: Interactive price markdown strategy & margin optimization.\n"
            "4. ⚡ **ML Flash Claims (Tab 4)**: Process incoming customer claims & NGO subsidies.\n\n"
            "Select a destination below to navigate immediately!"
        )
        quick = ["🎯 Demand Forecasting", "📊 Current Inventory Timeline", "🧪 ML Discount Simulator", "⚡ Flash Claims"]

    # Customer Intents
    elif intent == "greeting":
        reply = (
            "👋 Hi there! Welcome to **OptiMart** — your food-rescue marketplace.\n\n"
            "I can help you find discounted food products near you, guide you through claiming "
            "a deal, or answer questions about product safety and payment.\n\n"
            f"Right now there are **{n} deals** live. Check them out below! 🎉"
            if n > 0 else
            "👋 Hi there! Welcome to **OptiMart**. It looks like there are no active deals "
            "at the moment — check back soon, new batches get added daily!"
        )
        quick = ["Show me all discounts 🛒", "Dairy deals 🥛", "How do I claim? 🤝", "Bakery deals 🍞"]

    elif intent == "search_category":
        if n > 0:
            reply = (
                f"🔍 Found **{n} discounted {category}** item(s) right now.\n"
                "Here are the best deals — tap **Claim** on any card to reserve yours!"
            )
        else:
            reply = (
                f"😕 No discounted **{category}** products are available right now.\n"
                "Try another category or check back later — stock changes throughout the day!"
            )
        quick = ["Show all discounts 🛒", "How do I claim? 🤝", "Bakery deals 🍞", "Fruits & veggies 🥦"]

    elif intent == "claim_guide":
        reply = (
            "🤝 **How to claim a product:**\n\n"
            "1. Browse the deals below (or tell me a category you want)\n"
            "2. Tap **Claim** on any product card\n"
            "3. Enter your phone/email to reserve your slot (3-minute hold)\n"
            "4. Head to the store and pick up your order!\n\n"
            "Payment can be done in-store via UPI, cash, or card. "
            "NGOs and subsidized accounts may be eligible for further reductions.\n\n"
            "Want me to show you what's available right now?"
        )
        quick = ["Show all discounts 🛒", "Dairy deals 🥛", "Payment options 💳", "Is it safe to eat? 🍎"]

    elif intent == "expiry_faq":
        reply = (
            "🍎 **Food safety at OptiMart:**\n\n"
            "Every product listed on OptiMart has been inspected and is safe to eat — "
            "it's discounted because it's approaching its *best-before date*, not because it's spoiled.\n\n"
            "• Items marked **DISCOUNTED** are within their safe consumption window.\n"
            "• All batches are assessed daily using our ML engine (temperature, conditions, shelf-life).\n"
            "• If you're unsure, check the *expiry date* shown on each product card.\n\n"
            "Any products past expiry are automatically removed from the platform."
        )
        quick = ["Show me deals 🛒", "How do I claim? 🤝", "Payment options 💳"]

    elif intent == "payment_faq":
        reply = (
            "💳 **Payment & Pricing:**\n\n"
            "• Prices shown are the **final discounted prices** — no hidden charges.\n"
            "• Accepted modes: **UPI, Cash, Debit/Credit card** (at store).\n"
            "• NGO / community accounts may qualify for **additional subsidies** — "
            "mention this while claiming.\n"
            "• Discounts are set dynamically — the closer to expiry, the bigger the saving!\n\n"
            "Want to browse current deals?"
        )
        quick = ["Show all discounts 🛒", "How do I claim? 🤝", "Is it safe to eat? 🍎"]

    elif intent == "help":
        reply = (
            "🤖 **What I can help you with:**\n\n"
            "• 🛒 **Browse deals** — show current discounts, filter by category\n"
            "• 🤝 **Claim guide** — step-by-step on how to reserve & pick up\n"
            "• 🍎 **Food safety** — is the product safe? what does *near-expiry* mean?\n"
            "• 💳 **Payment** — accepted payment methods, NGO subsidies\n\n"
            "Just type a question or pick from the suggestions below!"
        )
        quick = ["Show all discounts 🛒", "Dairy deals 🥛", "How do I claim? 🤝", "Is it safe to eat? 🍎"]

    else:  # browse_discounts default
        if n > 0:
            reply = (
                f"🛒 Here are the **top {n} live deals** right now — freshest discounts first!"
            )
        else:
            reply = (
                "😕 No discounted products are live at the moment.\n"
                "New batches are added throughout the day — check back soon!"
            )
        quick = ["Dairy deals 🥛", "Bakery deals 🍞", "How do I claim? 🤝", "Fruits & veggies 🥦"]

    return ChatResponse(
        reply=reply,
        intent=intent,
        products=cards,
        quick_replies=quick,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """AI assistant chat endpoint powering the role-bifurcated widget.

    Detects intent based on message and user role (retailer vs customer),
    optionally fetches product cards for customers or analytics summaries for retailers.
    """
    role = req.role or "customer"
    intent, category = _detect_intent(req.message, role=role)

    # Fetch products for customer deal-display intents
    if role == "customer" and intent in ("greeting", "browse_discounts", "search_category"):
        products = _fetch_discounted_batches(
            db=db,
            category=category,
            store_id=req.store_id,
            limit=6,
        )
    else:
        products = []

    return _build_response(intent, category, products, req.message)


@router.get("/deals", response_model=ChatResponse)
def get_deals(
    role: Optional[str] = Query("customer"),
    category: Optional[str] = None,
    store_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Shortcut GET endpoint to fetch current welcome message without a chat message.
    Used by the widget on first load to populate initial cards/greeting.
    """
    if role == "retailer":
        return _build_response("retailer_greeting", None, [], "")

    products = _fetch_discounted_batches(db=db, category=category, store_id=store_id, limit=8)
    n = len(products)
    cards = [_batch_to_card(b) for b in products]
    reply = (
        f"👋 Welcome! Here are **{n} live deals** right now." if n > 0
        else "No active deals at the moment — check back soon!"
    )
    return ChatResponse(
        reply=reply,
        intent="browse_discounts",
        products=cards,
        quick_replies=_QUICK_DEFAULTS,
    )
