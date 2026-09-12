"""Completing 3D Secure 2 (3DS2) authentication challenges."""

import base64
import json

from pubstripe.client.request import request_stripe
from pubstripe.models import ThreeDSecureRequest, Proxy
from pubstripe.enums import ThreeDSecureStatus


THREE_D_SECURE_STATUS: dict[str, ThreeDSecureStatus] = {
    "Y": ThreeDSecureStatus.FRICTIONLESS,
    "N": ThreeDSecureStatus.FAILED,
    "U": ThreeDSecureStatus.UNAVAILABLE,
    "A": ThreeDSecureStatus.ATTEMPTED,
    "C": ThreeDSecureStatus.CHALLENGE,
    "R": ThreeDSecureStatus.REJECTED,
    "D": ThreeDSecureStatus.DECOUPLED,
    "I": ThreeDSecureStatus.INFORMATIONAL,
}
"""Maps the ACS's single-letter ``transStatus`` code to a :class:`~pubstripe.enums.ThreeDSecureStatus`."""


def b64_encode_fingerprint(transaction_id: str) -> str:
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


def get_browser_metadata(fingerprint: str) -> str:
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


async def authenticate_three_d_secure(
        request: ThreeDSecureRequest,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ThreeDSecureStatus:
    """Complete a 3D Secure 2 authentication challenge for an intent.

    Call this when :func:`pubstripe.intent.confirm_intent` (or one of its
    variants) returns ``status=REQUIRES_ACTION`` with a ``three_d_secure``
    payload. After this returns, call
    :func:`pubstripe.intent.complete_intent_after_3ds2` to get the intent's
    final status.

    Args:
        request: The 3DS2 challenge details from a
            :class:`~pubstripe.models.ConfirmIntentResponse`.
        publishable_key: The Stripe publishable key for the account that
            owns the intent.
        proxy: An optional proxy to route the request through.

    Returns:
        The authentication outcome as a
        :class:`~pubstripe.enums.ThreeDSecureStatus`.

    Raises:
        InvalidRequestError: If Stripe rejects the request as malformed.
        InvalidPublishableKey: If ``publishable_key`` is invalid.
        KeyError: If Stripe returns a ``transStatus`` code not present in
            :data:`THREE_D_SECURE_STATUS`.
    """
    url = "/v1/3ds2/authenticate"

    fingerprint = b64_encode_fingerprint(request.transaction_id)
    browser_metadata = get_browser_metadata(fingerprint)

    payload = {
        "source": request.source,
        "browser": browser_metadata,
        "key": publishable_key,
        "one_click_authn_device_support[hosted]": False,
        "one_click_authn_device_support[same_origin_frame]": False,
        "one_click_authn_device_support[spc_eligible]": False,
        "one_click_authn_device_support[webauthn_eligible]": True,
        "one_click_authn_device_support[publickey_credentials_get_allowed]": False
    }

    response = await request_stripe("POST", url, data=payload, proxy=proxy)
    data = response.json()

    transaction_code = data["ares"]["transStatus"]
    return THREE_D_SECURE_STATUS[transaction_code]
