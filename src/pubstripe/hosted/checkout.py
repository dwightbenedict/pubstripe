from pubstripe._utils import decline_response
from pubstripe.client.request import stripe_get, stripe_post
from pubstripe.models import CheckoutSession, ConfirmResponse, Intent, Proxy

from .context import CheckoutContext


async def get_checkout_session(ctx: CheckoutContext, proxy: Proxy | None = None) -> CheckoutSession:
    """Fetch a Checkout Session's total and customer details.

    Use ``session.total`` as the ``amount`` for :func:`confirm`, and
    :meth:`BillingDetails.from_checkout_session
    <pubstripe.billing_details.BillingDetails.from_checkout_session>` so the
    payment method's billing details match the session's customer.

    Args:
        ctx: The Checkout Session to look up, from
            :meth:`CheckoutContext.from_url`.
        proxy: An optional proxy to route the request through.

    Returns:
        The :class:`~pubstripe.models.CheckoutSession`.

    Raises:
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If the session's publishable key is invalid.
        curl_cffi.requests.exceptions.HTTPError: For any other error status.
    """
    path = f"/v1/payment_pages/{ctx.session_id}"
    params = {
        "key": ctx.publishable_key,
    }
    response = await stripe_get(path, params=params, proxy=proxy)
    response.raise_for_status()
    return CheckoutSession.model_validate(response.json())


async def confirm(
        payment_method_id: str,
        amount: int,
        ctx: CheckoutContext,
        proxy: Proxy | None = None,
) -> ConfirmResponse:
    """Confirm a Checkout Session with an existing payment method.

    The payment method's billing email must match the session's customer
    email, or Stripe rejects the confirmation with ``InvalidRequestError``
    (``customer_and_confirmation_email_mismatch``). Build the billing details
    with :meth:`BillingDetails.from_checkout_session
    <pubstripe.billing_details.BillingDetails.from_checkout_session>`.

    Unlike :mod:`pubstripe.intent`, a Checkout Session creates its intent
    itself, so there is no client secret to supply up front; the one Stripe
    created is returned.

    Args:
        payment_method_id: A payment method ID, e.g. from
            :func:`pubstripe.tokenization.create_payment_method`.
        amount: The session total, i.e. ``get_checkout_session(ctx).total``
            (``0`` for a trial or setup-mode session).
        ctx: The Checkout Session to confirm.
        proxy: An optional proxy to route the request through.

    Returns:
        A :class:`~pubstripe.models.ConfirmResponse` holding the session's
        intent. As with :func:`pubstripe.intent.confirm_with_payment_method`, a
        decline is returned (``error`` set, with ``intent`` only if Stripe
        attached one), not raised. If ``intent.status`` is
        ``requires_action``, pass ``intent.three_d_secure`` to
        :func:`pubstripe.three_d_secure.authenticate` and then
        ``client_secret`` to :func:`pubstripe.intent.retrieve`.

    Raises:
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If the session's publishable key is invalid.
        curl_cffi.requests.exceptions.HTTPError: For any other error status.
    """
    path = f"/v1/payment_pages/{ctx.session_id}/confirm"
    payload = {
        "payment_method": payment_method_id,
        "expected_payment_method_type": "card",
        "expected_amount": amount,
        "key": ctx.publishable_key
    }
    response = await stripe_post(path, data=payload, proxy=proxy)
    data = response.json()

    if response.status_code == 402:
        return decline_response(data)

    response.raise_for_status()
    intent = Intent.model_validate(data.get("setup_intent") or data.get("payment_intent"))
    return ConfirmResponse(intent=intent)
