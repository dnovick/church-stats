"""HTTP fetching for the scraper."""

from __future__ import annotations

import requests

USER_AGENT = "church-stats/0.1 (+https://github.com/dnovick/church-stats)"
DEFAULT_TIMEOUT_SECONDS = 15


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched or returns a non-success status."""


def fetch_page(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Fetch ``url`` and return its response body as text.

    Raises ``FetchError`` on network failure or a non-2xx status code.
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc

    if not response.ok:
        raise FetchError(f"Failed to fetch {url}: HTTP {response.status_code}")

    return response.text
