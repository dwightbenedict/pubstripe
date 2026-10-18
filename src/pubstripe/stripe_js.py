import re
import time

from curl_cffi.requests.exceptions import RequestException

from pubstripe.client.session import create_session
from pubstripe.exceptions import StripeJsUnavailable
from pubstripe.models import Proxy


STRIPE_JS_URL = "https://js.stripe.com/v3/"
CACHE_SECONDS = 3600

_BUILD_SALT = re.compile(r'STRIPE_JS_BUILD_SALT ([0-9a-f]{10})\*/"')
_cache: tuple[float, str] | None = None


async def get_version(proxy: Proxy | None = None) -> str:
    """Return the current Stripe.js build hash, e.g. ``"2bae21f786"``.

    The hash is read from the ``STRIPE_JS_BUILD_SALT`` marker in the script
    served at :data:`STRIPE_JS_URL` and cached for :data:`CACHE_SECONDS`.
    There is deliberately no fallback value: Stripe rotates the hash, so a
    stored one would go stale.

    Args:
        proxy: An optional proxy to route the lookup through.

    Returns:
        The 10-character build hash.

    Raises:
        StripeJsUnavailable: If the script can't be fetched or the build
            hash can't be found in it.
    """
    global _cache

    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]

    try:
        async with create_session(proxy.url if proxy else None) as session:
            response = await session.get(STRIPE_JS_URL)
        match = _BUILD_SALT.search(response.text)
    except RequestException as exc:
        raise StripeJsUnavailable(f"Could not fetch {STRIPE_JS_URL}: {exc}") from exc

    if response.status_code != 200 or not match:
        raise StripeJsUnavailable(f"Could not read the Stripe.js build hash from {STRIPE_JS_URL}.")

    _cache = (time.monotonic(), match.group(1))
    return _cache[1]


def payment_user_agent(version: str, *tags: str) -> str:
    """Build a ``payment_user_agent`` string.

    Stripe.js sends the bare ``stripe.js/<hash>; stripe-js-v3/<hash>`` for a
    plain call, adds an integration tag for an element (e.g.
    ``payment-element; deferred-intent``), and may append a context suffix
    such as ``autopm``. The tag comes from the integration being imitated, so
    callers choose it; it can't be read from the Stripe.js download.

    Args:
        version: The Stripe.js build hash from :func:`get_version`.
        *tags: Integration tags and suffixes to append, in order.

    Returns:
        For example ``"stripe.js/2bae21f786; stripe-js-v3/2bae21f786; payment-element"``.
    """
    return "; ".join([f"stripe.js/{version}", f"stripe-js-v3/{version}", *tags])
