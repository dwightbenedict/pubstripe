from dataclasses import dataclass
import base64
import json
import urllib.parse
from urllib.parse import urlsplit


XOR_KEY = 5
"""Single-byte XOR key Stripe applies to the base64 payload in a Checkout URL fragment."""


def decode_fragment(fragment: str) -> dict:
    """Decode the payload hidden in a hosted Checkout URL's ``#fragment``.

    The fragment is percent-encoded base64 (standard or URL-safe, padding
    optional) of a JSON object XOR-ed with :data:`XOR_KEY`.

    Args:
        fragment: The URL fragment, without the leading ``#``.

    Returns:
        The decoded JSON object.

    Raises:
        ValueError: If the fragment is not valid base64, or does not decode
            to a JSON object.
    """
    unquoted = urllib.parse.unquote(fragment)
    # tolerate both standard and URL-safe base64, and missing padding
    unquoted = unquoted.replace("-", "+").replace("_", "/")
    unquoted += "=" * (-len(unquoted) % 4)
    raw = base64.b64decode(unquoted)
    decoded = bytes(b ^ XOR_KEY for b in raw).decode("utf-8", errors="replace")

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        raise ValueError("Fragment did not decode to a JSON object.") from None

    if not isinstance(payload, dict):
        raise ValueError("Fragment did not decode to a JSON object.")

    return payload


@dataclass
class CheckoutContext:
    """The two values needed to talk to a hosted Checkout Session."""

    session_id: str
    """The Checkout Session ID, e.g. ``"cs_live_..."``."""
    publishable_key: str
    """The publishable key (``"pk_..."``) of the account that owns the session."""

    @classmethod
    def from_url(cls, url: str) -> "CheckoutContext":
        """Build a context from a hosted Checkout URL.

        Args:
            url: A ``https://checkout.stripe.com/c/pay/cs_...#...`` URL.
                The session ID is the last path segment and the publishable
                key lives in the encoded fragment.

        Returns:
            The parsed :class:`CheckoutContext`.

        Raises:
            ValueError: If the URL has no decodable fragment or the payload
                carries no ``apiKey``.
        """
        parts = urlsplit(url.strip())

        session_id = parts.path.rstrip("/").rsplit("/", 1)[-1]
        payload = decode_fragment(parts.fragment)

        try:
            publishable_key = payload["apiKey"]
        except KeyError:
            raise ValueError("Checkout URL payload has no 'apiKey'.") from None

        return cls(
            session_id=session_id,
            publishable_key=publishable_key,
        )
