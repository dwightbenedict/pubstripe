from pubstripe._utils import decline_response
from pubstripe.client.request import stripe_get, stripe_post
from pubstripe.exceptions import InvalidClientSecret
from pubstripe.models import ConfirmResponse, CreditCard, Intent, Proxy


def _intent_path(client_secret: str) -> str:
    """Build the ``/v1/<resource>/<id>`` API path for a client secret.

    The intent's ID is the part of the secret before ``_secret_``; its
    resource is inferred from that ID's prefix (``seti_`` for a SetupIntent,
    ``pi_`` for a PaymentIntent).

    Raises:
        InvalidClientSecret: If the prefix is neither ``seti_`` nor ``pi_``.
            The secret itself is left out of the message.
    """
    intent_id = client_secret.split("_secret_")[0]

    if intent_id.startswith("seti_"):
        return f"/v1/setup_intents/{intent_id}"

    if intent_id.startswith("pi_"):
        return f"/v1/payment_intents/{intent_id}"

    raise InvalidClientSecret("Invalid client secret: expected a 'seti_' or 'pi_' intent ID followed by '_secret_'.")


async def _confirm(
        payment_method_data: dict[str, str],
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ConfirmResponse:
    """Confirm a SetupIntent or PaymentIntent with arbitrary payment method data.

    This is the low-level building block behind
    :func:`confirm_with_credit_card` and
    :func:`confirm_with_payment_method`; use one of those unless you
    need to send custom ``payment_method_data[...]`` fields.

    Args:
        payment_method_data: The ``payment_method_data[...]`` (or
            ``payment_method``) fields to submit, in Stripe's flat form
            encoding.
        client_secret: The intent's client secret.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        A :class:`~pubstripe.models.ConfirmResponse`. A card decline is
        returned rather than raised: ``error`` is set, and ``intent`` too when
        Stripe attached one (some declines, e.g. an incorrect CVC, attach
        none). Otherwise ``intent`` is set; if its ``status`` is
        ``requires_action``, ``intent.three_d_secure`` is populated; pass it
        to :func:`pubstripe.three_d_secure.authenticate`.

    Raises:
        InvalidClientSecret: If ``client_secret`` cannot be parsed.
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
        curl_cffi.requests.exceptions.HTTPError: For any other error
            status (e.g. 404 or 5xx). A 402 card decline is *not* raised.
    """
    path = f"{_intent_path(client_secret)}/confirm"
    payload = {
        "expected_payment_method_type": "card",
        "key": publishable_key,
        "client_secret": client_secret
    }
    payload.update(payment_method_data)

    response = await stripe_post(path, data=payload, proxy=proxy)
    data = response.json()

    if response.status_code == 402:
        return decline_response(data)

    response.raise_for_status()
    return ConfirmResponse(intent=Intent.model_validate(data))


async def confirm_with_credit_card(
        card: CreditCard,
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ConfirmResponse:
    """Confirm a SetupIntent or PaymentIntent by submitting raw card details.

    Args:
        card: The credit card to confirm the intent with.
        client_secret: The intent's client secret.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        See :func:`_confirm`.

    Raises:
        InvalidClientSecret: If ``client_secret`` cannot be parsed.
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
    """
    payment_method_data = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": card.number,
        "payment_method_data[card][exp_month]": card.exp_month,
        "payment_method_data[card][exp_year]": card.exp_year
    }

    if card.cvc:
        payment_method_data["payment_method_data[card][cvc]"] = card.cvc

    return await _confirm(payment_method_data, client_secret, publishable_key, proxy)


async def confirm_with_payment_method(
        payment_method: str,
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ConfirmResponse:
    """Confirm a SetupIntent or PaymentIntent using an existing payment method ID.

    Args:
        payment_method: An existing Stripe payment method ID, e.g. from
            :func:`pubstripe.tokenization.create_payment_method`.
        client_secret: The intent's client secret.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        See :func:`_confirm`.

    Raises:
        InvalidClientSecret: If ``client_secret`` cannot be parsed.
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
    """
    payment_method_data = {
        "payment_method": payment_method
    }
    return await _confirm(payment_method_data, client_secret, publishable_key, proxy)


async def retrieve(
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> Intent:
    """Fetch an intent as Stripe currently sees it.

    Call this after :func:`pubstripe.three_d_secure.authenticate`
    returns, then check ``status`` (``succeeded`` on success, otherwise see
    ``last_payment_error`` / ``last_setup_error``).

    Args:
        client_secret: The intent's client secret.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        The :class:`~pubstripe.models.Intent`, exactly as Stripe reports it.

    Raises:
        InvalidClientSecret: If ``client_secret`` cannot be parsed.
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
        curl_cffi.requests.exceptions.HTTPError: For any other error status.
    """
    path = _intent_path(client_secret)
    params = {
        "key": publishable_key,
        "client_secret": client_secret
    }

    response = await stripe_get(path, params=params, proxy=proxy)
    response.raise_for_status()
    return Intent.model_validate(response.json())
