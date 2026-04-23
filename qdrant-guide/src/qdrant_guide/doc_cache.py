"""HTTP fetcher with in-memory TTL cache for Qdrant documentation pages."""

import time

import httpx
from markdownify import markdownify as md

from .config import DOC_CACHE_TTL_SECONDS, DOC_MAX_CHARS, LLMS_TXT_URL


class DocCache:
    """Fetches and caches Qdrant documentation pages.

    Pages are converted from HTML to markdown and cached in memory
    with a configurable TTL. The llms.txt index is fetched once and
    kept for the lifetime of the cache.
    """

    def __init__(self, ttl_seconds: int = DOC_CACHE_TTL_SECONDS):
        self._cache: dict[str, tuple[str, float]] = {}
        self._ttl = ttl_seconds
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "qdrant-guide/0.1.0"},
        )
        self._llms_txt: str | None = None

    async def fetch_llms_txt(self) -> str:
        """Fetch and cache the llms.txt doc index."""
        if self._llms_txt is None:
            resp = await self._client.get(LLMS_TXT_URL)
            resp.raise_for_status()
            self._llms_txt = resp.text
        return self._llms_txt

    async def fetch_page(self, url: str) -> str:
        """Fetch a doc page, convert HTML to markdown, cache the result.

        Returns cached content if still within TTL. HTML pages are
        converted to markdown with script/style/nav/footer tags stripped.
        Content is truncated at DOC_MAX_CHARS to stay within context limits.
        """
        now = time.time()
        if url in self._cache:
            content, cached_at = self._cache[url]
            if now - cached_at < self._ttl:
                return content

        resp = await self._client.get(url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            content = md(
                resp.text,
                strip=["script", "style", "nav", "footer", "header"],
            )
        else:
            content = resp.text

        if len(content) > DOC_MAX_CHARS:
            content = (
                content[:DOC_MAX_CHARS]
                + "\n\n[Content truncated. Fetch a more specific sub-page for details.]"
            )

        self._cache[url] = (content, now)
        return content

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
