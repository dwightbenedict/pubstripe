from pubstripe.billing_details import BillingDetails
from pubstripe.client.request import stripe_post
from pubstripe.models import CreditCard, Proxy, TokenizationResponse
from pubstripe.stripe_js import get_version, payment_user_agent


PAYMENT_ELEMENT_TAGS = ("payment-element", "deferred-intent")
"""Integration tags Stripe.js sends for a Payment Element created before its intent exists."""


async def _tokenize(
        path: str,
        payment_config: dict[str, str | int],
        proxy: Proxy | None = None
) -> TokenizationResponse:
    """Submit tokenization data to Stripe and return its reply.

    This is the shared implementation behind :func:`create_payment_method`
    and :func:`create_confirmation_token`; use one of those unless you need
    to hit a custom tokenization endpoint.

    Args:
        path: The Stripe API path to POST to, e.g. ``"/v1/payment_methods"``.
        payment_config: The form-encoded payload to submit.
        proxy: An optional proxy to route the request through.

    Returns:
        A :class:`~pubstripe.models.TokenizationResponse` with the created
        object's ``id``, or the ``error`` if Stripe declined the card (HTTP
        402). A decline is returned, not raised.

    Raises:
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If the publishable key in ``payment_config``
            is invalid.
        curl_cffi.requests.exceptions.HTTPError: For any other error status.
    """
    response = await stripe_post(path, data=payment_config, proxy=proxy)

    if response.status_code != 402:
        response.raise_for_status()

    return TokenizationResponse.model_validate(response.json())


async def create_payment_method(
        card: CreditCard,
        publishable_key: str,
        billing_details: BillingDetails | None = None,
        proxy: Proxy | None = None
) -> TokenizationResponse:
    """Tokenize a credit card into a reusable Stripe payment method.

    The resulting payment method ID can be confirmed against an intent with
    :func:`pubstripe.intent.confirm_with_payment_method`.

    Args:
        card: The credit card to tokenize.
        publishable_key: The Stripe publishable key for the account this
            payment method should belong to.
        billing_details: The cardholder's billing details. Random US
            details are generated when omitted.
        proxy: An optional proxy to route the request through.

    Returns:
        A :class:`~pubstripe.models.TokenizationResponse`: ``id`` is the new
        payment method's ID (``"pm_..."``), or ``error`` says why Stripe
        declined the card.

    Raises:
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
        StripeJsUnavailable: If the current Stripe.js build can't be determined.
    """
    path = "/v1/payment_methods"
    payload = {
        "type": "card",
        "card[number]": card.number,
        "card[exp_month]": card.exp_month,
        "card[exp_year]": card.exp_year,
        "key": publishable_key,
        "payment_user_agent": payment_user_agent(await get_version(proxy), *PAYMENT_ELEMENT_TAGS)
    }

    payload.update(
        (billing_details or BillingDetails()).to_params("billing_details")
    )

    if card.cvc:
        payload["card[cvc]"] = card.cvc

    return await _tokenize(path, payload, proxy=proxy)


async def create_confirmation_token(
        card: CreditCard,
        publishable_key: str,
        billing_details: BillingDetails | None = None,
        proxy: Proxy | None = None
) -> TokenizationResponse:
    """Tokenize a credit card into a one-time-use Stripe confirmation token.

    Unlike :func:`create_payment_method`, a confirmation token bundles the
    payment method with confirmation-time data in a single object intended
    for immediate use.

    Args:
        card: The credit card to tokenize.
        publishable_key: The Stripe publishable key for the account this
            confirmation token should belong to.
        billing_details: The cardholder's billing details. Random US
            details are generated when omitted.
        proxy: An optional proxy to route the request through.

    Returns:
        A :class:`~pubstripe.models.TokenizationResponse`: ``id`` is the new
        confirmation token's ID (``"ctoken_..."``), or ``error`` says why
        Stripe declined the card.

    Raises:
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
        StripeJsUnavailable: If the current Stripe.js build can't be determined.
    """
    path = "/v1/confirmation_tokens"
    payload = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": card.number,
        "payment_method_data[card][exp_year]": card.exp_year,
        "payment_method_data[card][exp_month]": card.exp_month,
        "payment_method_data[payment_user_agent]": payment_user_agent(await get_version(proxy), *PAYMENT_ELEMENT_TAGS, "autopm"),
        "key": publishable_key,
    }

    payload.update(
        (billing_details or BillingDetails()).to_params("payment_method_data[billing_details]")
    )

    if card.cvc:
        payload["payment_method_data[card][cvc]"] = card.cvc

    return await _tokenize(path, payload, proxy=proxy)
