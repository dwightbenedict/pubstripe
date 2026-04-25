from typing import Any

from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import HTTPError, ConnectionError, Timeout
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type
)

from pubstripe.core.settings import settings
from pubstripe.exceptions import InvalidRequestError, InvalidPublishableKey

from .session import create_session


@retry(
    stop=stop_after_attempt(settings.http.max_retries),
    wait=wait_exponential_jitter(max=settings.http.max_retry_delay),
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

    response.raise_for_status()
    return response