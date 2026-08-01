"""Multi-rail payment service supporting Razorpay and Stripe (test mode).

Both providers fall back to a mock checkout link when API credentials are
absent or contain placeholder values — ensuring tests and local demos work
without live keys. All amounts are handled in smallest currency units
(paise for INR / Razorpay, cents for INR / Stripe).
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


def _is_configured(key: str, secret: str) -> bool:
    return bool(key and secret and "HERE" not in key and "HERE" not in secret)


# ── Razorpay ─────────────────────────────────────────────────────────────────

def create_razorpay_order(
    amount_paise: int,
    claim_token: str,
    currency: str = "INR",
) -> Dict[str, Any]:
    """Creates a Razorpay test-mode order. Returns mock data if unconfigured."""
    if _is_configured(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET):
        try:
            import razorpay
            client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            order = client.order.create(
                {
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": f"nexpire_{claim_token[:12]}",
                    "notes": {"claim_token": claim_token},
                }
            )
            return {
                "provider": "razorpay",
                "checkout_url": f"https://rzp.io/l/{order['id']}",
                "order_id": order["id"],
                "amount_paise": amount_paise,
                "amount_cents": None,
                "currency": currency,
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
            }
        except Exception as e:
            print(f"Razorpay order creation failed ({e}), falling back to mock.")

    mock_order_id = f"order_{uuid.uuid4().hex[:12]}"
    return {
        "provider": "razorpay",
        "checkout_url": f"https://rzp.io/l/{mock_order_id}",
        "order_id": mock_order_id,
        "amount_paise": amount_paise,
        "amount_cents": None,
        "currency": currency,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
    }


def verify_razorpay_webhook(body: bytes, signature: str) -> bool:
    """Verifies Razorpay webhook HMAC signature. Returns True in mock mode."""
    if not RAZORPAY_WEBHOOK_SECRET or "here" in RAZORPAY_WEBHOOK_SECRET.lower():
        return True
    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        client.utility.verify_webhook_signature(body.decode(), signature, RAZORPAY_WEBHOOK_SECRET)
        return True
    except Exception:
        return False


# ── Stripe ────────────────────────────────────────────────────────────────────

def create_stripe_session(
    amount_cents: int,
    claim_token: str,
    currency: str = "inr",
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a Stripe Checkout Session. Returns mock data if unconfigured."""
    success_url = success_url or f"{BACKEND_URL}/claim/success"
    cancel_url = cancel_url or f"{BACKEND_URL}/claim/cancel"

    if _is_configured(STRIPE_API_KEY, STRIPE_API_KEY):
        try:
            import stripe
            stripe.api_key = STRIPE_API_KEY
            session = stripe.checkout.Session.create(
                line_items=[
                    {
                        "price_data": {
                            "currency": currency,
                            "unit_amount": amount_cents,
                            "product_data": {"name": f"NEXPIRE Claim {claim_token[:8]}"},
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"claim_token": claim_token},
            )
            return {
                "provider": "stripe",
                "checkout_url": session.url,
                "order_id": session.id,
                "amount_paise": None,
                "amount_cents": amount_cents,
                "currency": currency,
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
            }
        except Exception as e:
            print(f"Stripe session creation failed ({e}), falling back to mock.")

    mock_session_id = f"cs_test_{uuid.uuid4().hex[:24]}"
    return {
        "provider": "stripe",
        "checkout_url": f"https://checkout.stripe.com/pay/{mock_session_id}",
        "order_id": mock_session_id,
        "amount_paise": None,
        "amount_cents": amount_cents,
        "currency": currency,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
    }


def verify_stripe_webhook(body: bytes, signature: str) -> bool:
    """Verifies Stripe webhook signature. Returns True in mock mode."""
    if not STRIPE_WEBHOOK_SECRET or "here" in STRIPE_WEBHOOK_SECRET.lower():
        return True
    try:
        import stripe
        stripe.api_key = STRIPE_API_KEY
        stripe.Webhook.construct_event(body, signature, STRIPE_WEBHOOK_SECRET)
        return True
    except Exception:
        return False
