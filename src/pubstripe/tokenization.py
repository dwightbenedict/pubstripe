"""Tokenizing raw card details into Stripe payment methods and confirmation tokens."""

from pubstripe.client.request import request_stripe
from pubstripe.models import CreditCard, Proxy
from pubstripe.exceptions import InvalidPaymentMethod


async def create_token(
        uri: str,
        payment_config: dict[str, str | int],
        proxy: Proxy | None = None
) -> str:
    """Submit tokenization data to Stripe and return the resulting object's ID.

    This is the shared implementation behind :func:`create_payment_method`
    and :func:`create_confirmation_token`; use one of those unless you need
    to hit a custom tokenization endpoint.

    Args:
        uri: The Stripe API path to POST to, e.g. ``"/v1/payment_methods"``.
        payment_config: The form-encoded payload to submit.
        proxy: An optional proxy to route the request through.

    Returns:
        The ``id`` of the created object (e.g. a payment method or
        confirmation token ID).

    Raises:
        InvalidPaymentMethod: If Stripe declines the card (HTTP 402).
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If the publishable key in ``payment_config``
            is invalid.
    """
    response = await request_stripe("POST", uri, data=payment_config, proxy=proxy)
    data = response.json()

    if response.status_code == 402:
        raise InvalidPaymentMethod(data["error"]["message"])

    response.raise_for_status()
    return data["id"]


async def create_payment_method(
        card: CreditCard,
        publishable_key: str,
        proxy: Proxy | None = None
) -> str:
    """Tokenize a credit card into a reusable Stripe payment method.

    The resulting payment method ID can be confirmed against an intent with
    :func:`pubstripe.intent.confirm_intent_with_payment_method`.

    Args:
        card: The credit card to tokenize.
        publishable_key: The Stripe publishable key for the account this
            payment method should belong to.
        proxy: An optional proxy to route the request through.

    Returns:
        The new payment method's ID (``"pm_..."``).

    Raises:
        InvalidPaymentMethod: If Stripe declines the card.
    """
    uri = "/v1/payment_methods"
    payload = {
        "type": "card",
        "card[number]": card.number,
        "card[exp_month]": card.exp_month,
        "card[exp_year]": card.exp_year,
        "key": publishable_key,
        "payment_user_agent": "stripe.js/668d00c08a; stripe-js-v3/668d00c08a; payment-element; deferred-intent"
    }

    if card.cvc:
        payload["card[cvc]"] = card.cvc

    return await create_token(uri, payload, proxy=proxy)


async def create_confirmation_token(
        card: CreditCard,
        publishable_key: str,
        proxy: Proxy | None = None
) -> str:
    """Tokenize a credit card into a one-time-use Stripe confirmation token.

    Unlike :func:`create_payment_method`, a confirmation token bundles the
    payment method with confirmation-time data in a single object intended
    for immediate use.

    Args:
        card: The credit card to tokenize.
        publishable_key: The Stripe publishable key for the account this
            confirmation token should belong to.
        proxy: An optional proxy to route the request through.

    Returns:
        The new confirmation token's ID (``"ctoken_..."``).

    Raises:
        InvalidPaymentMethod: If Stripe declines the card.
    """
    uri = "/v1/confirmation_tokens"
    payload = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": card.number,
        "payment_method_data[card][exp_year]": card.exp_year,
        "payment_method_data[card][exp_month]": card.exp_month,
        "payment_method_data[payment_user_agent]": "stripe.js/668d00c08a; stripe-js-v3/668d00c08a; payment-element; deferred-intent; autopm",
        "key": publishable_key,
    }

    if card.cvc:
        payload["payment_method_data[card][cvc]"] = card.cvc


    return await create_token(uri, payload, proxy=proxy)
