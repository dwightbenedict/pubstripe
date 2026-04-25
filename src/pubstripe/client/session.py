from contextlib import asynccontextmanager
from typing import AsyncGenerator

from curl_cffi import requests


BASE_URL = "https://api.stripe.com"
HEADERS = {
    "Referer": "https://js.stripe.com/",
    "Origin": "https://js.stripe.com"
}


@asynccontextmanager
async def create_session(proxy: str | None = None) -> AsyncGenerator[requests.AsyncSession, None]:
    async with requests.AsyncSession(
        base_url=BASE_URL,
        headers=HEADERS,
        impersonate="chrome",
        http_version="v2",
        proxy=proxy,
        timeout=20.0,
        verify=False
    ) as session:
        yield session