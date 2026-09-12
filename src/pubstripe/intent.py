from pubstripe.client.request import request_stripe
from pubstripe.models import (
    CreditCard,
    Proxy,
    Intent,
    ThreeDSecureRequest,
    ConfirmIntentResponse,
    CompleteIntentResponse
)
from pubstripe.enums import IntentType, ConfirmIntentStatus, CompleteIntentStatus
from pubstripe.exceptions import InvalidClientSecret


def intent_from_client_secret(client_secret: str) -> Intent:
    """Parse an :class:`~pubstripe.models.Intent` out of a raw client secret.

    The intent's ID is the part of the secret before ``_secret_``, and its
    type is inferred from that ID's prefix (``seti_`` for a SetupIntent,
    ``pi_`` for a PaymentIntent).

    Args:
        client_secret: The client secret from a SetupIntent or PaymentIntent,
            e.g. ``"pi_..._secret_..."``.

    Returns:
        The parsed :class:`~pubstripe.models.Intent`.

    Raises:
        InvalidClientSecret: If the secret's prefix matches neither
            ``seti_`` nor ``pi_``.
    """
    intent_id = client_secret.split("_secret_")[0]

    if intent_id.startswith("seti_"):
        intent_type = IntentType.SETUP_INTENT
    elif intent_id.startswith("pi_"):
        intent_type = IntentType.PAYMENT_INTENT
    else:
        raise InvalidClientSecret(f"Invalid client secret: {client_secret}")

    return Intent(
        id=intent_id,
        type=intent_type
    )


async def confirm_intent(
        payment_method_data: dict[str, str],
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ConfirmIntentResponse:
    """Confirm a SetupIntent or PaymentIntent with arbitrary payment method data.

    This is the low-level building block behind
    :func:`confirm_intent_with_credit_card` and
    :func:`confirm_intent_with_payment_method`; use one of those unless you
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
        A :class:`~pubstripe.models.ConfirmIntentResponse` describing whether
        confirmation succeeded, was declined, or requires a 3D Secure 2
        challenge (in which case ``three_d_secure`` is populated — pass it
        to :func:`pubstripe.three_d_secure.authenticate_three_d_secure`).

    Raises:
        InvalidClientSecret: If ``client_secret`` cannot be parsed.
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
    """
    intent = intent_from_client_secret(client_secret)

    uri = f"/v1/{intent.resource}/{intent.id}/confirm"
    payload = {
        "expected_payment_method_type": "card",
        "key": publishable_key,
        "client_secret": client_secret
    }
    payload.update(payment_method_data)

    response = await request_stripe("POST", uri, data=payload, proxy=proxy)
    data = response.json()

    if response.status_code == 402:
        error = data["error"]

        return ConfirmIntentResponse(
            intent=intent,
            payment_method_data=payment_method_data,
            status=ConfirmIntentStatus.FAILED,
            code=error.get("decline_code") or error.get("code"),
            message=error["message"],
        )

    response.raise_for_status()

    if data["status"] == "requires_action":
        three_d_secure_sdk = data["next_action"]["use_stripe_sdk"]
        three_d_secure = ThreeDSecureRequest(
            transaction_id=three_d_secure_sdk["server_transaction_id"],
            source=three_d_secure_sdk["three_d_secure_2_source"],
        )
        return ConfirmIntentResponse(
            intent=intent,
            payment_method_data=payment_method_data,
            status=ConfirmIntentStatus.REQUIRES_ACTION,
            code="stripe_3ds2_fingerprint",
            message="Must authenticate with 3D Secure 2.",
            three_d_secure=three_d_secure
        )

    return ConfirmIntentResponse(
        intent=intent,
        payment_method_data=payment_method_data,
        status=ConfirmIntentStatus.SUCCEEDED,
        code=data["status"],
        message="Payment method has been successfully validated."
    )


async def confirm_intent_with_credit_card(
        card: CreditCard,
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ConfirmIntentResponse:
    """Confirm a SetupIntent or PaymentIntent by submitting raw card details.

    Args:
        card: The credit card to confirm the intent with.
        client_secret: The intent's client secret.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        See :func:`confirm_intent`.
    """
    payment_method_data = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": card.number,
        "payment_method_data[card][exp_month]": card.exp_month,
        "payment_method_data[card][exp_year]": card.exp_year
    }

    if card.cvc:
        payment_method_data["payment_method_data[card][cvc]"] = card.cvc

    confirmation = await confirm_intent(payment_method_data, client_secret, publishable_key, proxy)
    return confirmation


async def confirm_intent_with_payment_method(
        payment_method: str,
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ConfirmIntentResponse:
    """Confirm a SetupIntent or PaymentIntent using an existing payment method ID.

    Args:
        payment_method: An existing Stripe payment method ID, e.g. from
            :func:`pubstripe.tokenization.create_payment_method`.
        client_secret: The intent's client secret.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        See :func:`confirm_intent`.
    """
    payment_method_data = {
        "payment_method": payment_method
    }
    confirmation = await confirm_intent(payment_method_data, client_secret, publishable_key, proxy)
    return confirmation


async def complete_intent_after_3ds2(
        client_secret: str,
        publishable_key: str,
        proxy: Proxy | None = None
) -> CompleteIntentResponse:
    """Check an intent's final status after a 3D Secure 2 challenge has completed.

    Call this after :func:`pubstripe.three_d_secure.authenticate_three_d_secure`
    returns, to find out whether the intent ultimately succeeded.

    Args:
        client_secret: The intent's client secret.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        A :class:`~pubstripe.models.CompleteIntentResponse` describing the
        intent's final status.

    Raises:
        InvalidClientSecret: If ``client_secret`` cannot be parsed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
    """
    intent = intent_from_client_secret(client_secret)
    uri = f"/v1/{intent.resource}/{intent.id}"
    params = {
        "key": publishable_key,
        "client_secret": client_secret
    }

    response = await request_stripe("GET", uri, params=params, proxy=proxy)
    response.raise_for_status()
    data = response.json()

    if data["status"] == "requires_payment_method":
        error = data.get("last_payment_error") or data.get("last_setup_error")
        return CompleteIntentResponse(
            intent=intent,
            status=CompleteIntentStatus.FAILED,
            code=error.get("decline_code") or error.get("code"),
            message=error["message"],
        )

    if data["status"] != "succeeded":
        return CompleteIntentResponse(
            intent=intent,
            status=CompleteIntentStatus.FAILED,
            code=data["status"],
            message="Failed to complete the intent."
        )

    return CompleteIntentResponse(
        intent=intent,
        status=CompleteIntentStatus.SUCCEEDED,
        code=data["status"],
        message="Intent completed."
    )
