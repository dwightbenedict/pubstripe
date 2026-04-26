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


def b64_encode_fingerprint(transaction_id: str) -> str:
    fingerprint = {
        "threeDSServerTransID": transaction_id
    }
    encoded = base64.b64encode(
        json.dumps(fingerprint).encode("utf-8")
    )
    return encoded.decode("utf-8")


def get_browser_metadata(fingerprint: str) -> str:
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
        request:ThreeDSecureRequest,
        publishable_key: str,
        proxy: Proxy | None = None
) -> ThreeDSecureStatus:
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