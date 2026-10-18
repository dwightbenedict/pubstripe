from typing import Any

from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import HTTPError, ConnectionError, Timeout
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type
)

from pubstripe.exceptions import InvalidRequestError, InvalidPublishableKey
from pubstripe.models import Proxy

from .session import create_session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(max=3.0),
    retry=retry_if_exception_type(
        (
            HTTPError,
            ConnectionError,
            Timeout,
        )
    ),
    reraise=True
)
async def _request(
    session: AsyncSession,
    method: str,
    path: str,
    **kwargs: Any,
) -> Response:
    """Send a single HTTP request, retrying up to 3 times on transient failures.

    Retries on ``HTTPError``, ``ConnectionError``, and ``Timeout`` with
    jittered exponential backoff (capped at 3 seconds between attempts).
    If every attempt fails, the last exception is re-raised as-is.

    Args:
        session: An open session, typically from
            :func:`~pubstripe.client.session.create_session`.
        method: The HTTP method, e.g. ``"GET"`` or ``"POST"`` (case-insensitive).
        path: The request path or full URL.
        **kwargs: Extra keyword arguments forwarded to ``session.request``
            (e.g. ``data``, ``params``, ``proxy``).

    Returns:
        The raw HTTP response.
    """
    return await session.request(
        method=method.upper(),
        url=path,
        **kwargs,
    )


def _error_message(response: Response) -> str:
    """Describe a Stripe error response, tolerating non-JSON bodies.

    Returns Stripe's ``error.message``, followed by the error ``code`` and
    any ``extra_fields`` (e.g. a Checkout ``confirm_error_reason``) in
    brackets, since the message alone is often generic.
    """
    try:
        error = response.json()["error"]
        message = error["message"]
    except (ValueError, KeyError, TypeError):
        return f"Stripe returned HTTP {response.status_code}."

    details = [str(error["code"])] if error.get("code") else []
    details += [f"{key}={value}" for key, value in (error.get("extra_fields") or {}).items()]

    return f"{message} [{', '.join(details)}]" if details else message


async def request_stripe(
    method: str,
    path: str,
    proxy: Proxy | None = None,
    **kwargs: Any,
) -> Response:
    """Open a session, make one request to Stripe, and translate error responses.

    This is the entry point used by every pubstripe function that talks to
    Stripe: it opens a short-lived session via
    :func:`~pubstripe.client.session.create_session`, sends the request
    through :func:`_request`, and raises a pubstripe exception for the
    error statuses common to publishable-key requests.

    Args:
        method: The HTTP method, e.g. ``"GET"`` or ``"POST"``.
        path: The request path, relative to Stripe's API base URL.
        proxy: An optional proxy to route the session through.
        **kwargs: Extra keyword arguments forwarded to the session request,
            such as ``data`` or ``params``.

    Returns:
        The HTTP response, for status codes other than 400/401. Other error
        statuses (e.g. 402) are returned as-is for the caller to handle.

    Raises:
        InvalidRequestError: If Stripe responds ``400 Bad Request``.
        InvalidPublishableKey: If Stripe responds ``401 Unauthorized``.
    """
    async with create_session(proxy.url if proxy else None) as session:
        response = await _request(
            session=session,
            method=method,
            path=path,
            **kwargs,
        )

    status_code = response.status_code

    if status_code == 400:
        raise InvalidRequestError(_error_message(response))

    if status_code == 401:
        raise InvalidPublishableKey(_error_message(response))

    return response


async def stripe_get(path: str, **kwargs: Any) -> Response:
    """Send a ``GET`` to Stripe. Shorthand for :func:`request_stripe` with ``method="GET"``."""
    return await request_stripe("GET", path=path, **kwargs)


async def stripe_post(path: str, **kwargs: Any) -> Response:
    """Send a ``POST`` to Stripe. Shorthand for :func:`request_stripe` with ``method="POST"``."""
    return await request_stripe("POST", path=path, **kwargs)
