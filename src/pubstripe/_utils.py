from typing import Any

from pubstripe.models import ConfirmResponse, Intent, StripeError


def decline_response(body: dict[str, Any]) -> ConfirmResponse:
    """Build a :class:`~pubstripe.models.ConfirmResponse` from a card-error (HTTP 402) body.

    Stripe puts the error under ``error``, and usually embeds the failed
    intent in ``error.payment_intent`` or ``error.setup_intent``. Some
    declines (e.g. an incorrect CVC) embed none, in which case ``intent`` is
    ``None``.

    Args:
        body: The decoded JSON body of the 402 response.

    Returns:
        A response with ``error`` set, and ``intent`` set when one was embedded.
    """
    error = body.get("error") or {}
    intent = error.get("payment_intent") or error.get("setup_intent")

    return ConfirmResponse(
        intent=Intent.model_validate(intent) if intent else None,
        error=StripeError.model_validate(error),
    )
