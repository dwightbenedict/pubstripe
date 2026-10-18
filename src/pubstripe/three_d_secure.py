import base64
import json

from pubstripe.client.request import stripe_post
from pubstripe.models import Proxy, ThreeDSecureRequest, ThreeDSecureResponse


def _b64_encode_fingerprint(transaction_id: str) -> str:
    """Build the base64-encoded 3DS2 device fingerprint Stripe expects.

    Args:
        transaction_id: The 3DS2 server transaction ID
            (``ThreeDSecureRequest.transaction_id``).

    Returns:
        A base64-encoded JSON object of the form
        ``{"threeDSServerTransID": transaction_id}``.
    """
    fingerprint = {
        "threeDSServerTransID": transaction_id
    }
    encoded = base64.b64encode(
        json.dumps(fingerprint).encode("utf-8")
    )
    return encoded.decode("utf-8")


def _build_browser_metadata(fingerprint: str) -> str:
    """Build the browser metadata JSON string Stripe expects for a 3DS2 challenge.

    The values describe a stock desktop Firefox browser so the request
    matches what Stripe.js would normally send from an actual browser.

    Args:
        fingerprint: The encoded fingerprint from :func:`b64_encode_fingerprint`.

    Returns:
        A compact JSON string of browser metadata, ready to submit as the
        ``browser`` form field.
    """
    browser = {
        "fingerprintAttempted": True,
        "fingerprintData": fingerprint,
        "challengeWindowSize": None,
        "threeDSCompInd": "Y",
        "browserJavaEnabled": False,
        "browserJavascriptEnabled": True,
        "browserLanguage": "en-US",
        "browserColorDepth": "24",
        "browserScreenHeight": "1080",
        "browserScreenWidth": "1920",
        "browserTZ": "240",
        "browserUserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"
    }
    return json.dumps(browser, separators=(",", ":"))


async def authenticate(
        request: ThreeDSecureRequest,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ThreeDSecureResponse:
    """Start a 3D Secure 2 authentication challenge for an intent.

    Call this when a confirmation (:func:`pubstripe.intent.confirm_with_credit_card`,
    :func:`pubstripe.intent.confirm_with_payment_method` or
    :func:`pubstripe.hosted.checkout.confirm`) returns
    a :class:`~pubstripe.models.ConfirmResponse` whose ``intent`` has
    ``status`` of ``requires_action`` and a ``three_d_secure`` payload. After this
    returns, call :func:`pubstripe.intent.retrieve` to get the intent's
    final status.

    Args:
        request: The 3DS2 challenge details, i.e. the ``three_d_secure``
            field of a :class:`~pubstripe.models.Intent`.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        A :class:`~pubstripe.models.ThreeDSecureResponse`; the outcome is
        ``trans_status``, a :class:`~pubstripe.enums.ThreeDSecureStatus`.

    Raises:
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
        pydantic.ValidationError: If the response has no ``ares.transStatus``,
            or a code that :class:`~pubstripe.enums.ThreeDSecureStatus` lacks.
    """
    path = "/v1/3ds2/authenticate"
    fingerprint = _b64_encode_fingerprint(request.transaction_id)
    payload = {
        "source": request.source,
        "browser": _build_browser_metadata(fingerprint),
        "key": publishable_key,
    }
    response = await stripe_post(path, data=payload, proxy=proxy)
    return ThreeDSecureResponse.model_validate(response.json())
