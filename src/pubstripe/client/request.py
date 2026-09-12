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
async def send_request(
    session: AsyncSession,
    method: str,
    url: str,
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
        url: The request path or full URL.
        **kwargs: Extra keyword arguments forwarded to ``session.request``
            (e.g. ``data``, ``params``, ``proxy``).

    Returns:
        The raw HTTP response.
    """
    return await session.request(
        method=method.upper(),
        url=url,
        **kwargs,
    )


async def request_stripe(
    method: str,
    url: str,
    **kwargs: Any,
) -> Response:
    """Open a session, make one request to Stripe, and translate error responses.

    This is the entry point used by every pubstripe function that talks to
    Stripe: it opens a short-lived session via
    :func:`~pubstripe.client.session.create_session`, sends the request
    through :func:`send_request`, and raises a pubstripe exception for the
    error statuses common to publishable-key requests.

    Args:
        method: The HTTP method, e.g. ``"GET"`` or ``"POST"``.
        url: The request path, relative to Stripe's API base URL.
        **kwargs: Extra keyword arguments forwarded to the session request,
            such as ``data``, ``params``, or ``proxy``.

    Returns:
        The HTTP response, for status codes other than 400/401.

    Raises:
        InvalidRequestError: If Stripe responds ``400 Bad Request``.
        InvalidPublishableKey: If Stripe responds ``401 Unauthorized``.
    """
    async with create_session() as session:
        response = await send_request(
            session=session,
            method=method,
            url=url,
            **kwargs,
        )

    status_code = response.status_code
    data = response.json()

    if status_code == 400:
        raise InvalidRequestError(data["error"]["message"])

    if status_code == 401:
        raise InvalidPublishableKey(data["error"]["message"])

    return response
