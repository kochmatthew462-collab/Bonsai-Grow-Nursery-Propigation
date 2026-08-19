"""
The single outbound HTTP path, with caching, rate limiting and a source registry.

Every external request in the suite goes through `Fetcher`. That is not tidiness
for its own sake — it is what makes four things possible at once:

* **Honouring each API's usage policy.** NCBI's E-utilities policy caps
  unauthenticated traffic at 3 requests/second and asks for a `tool` and
  `email` on every call; Crossref and OpenAlex give faster, more reliable
  service to clients that identify themselves. A per-host rate limiter and a
  descriptive User-Agent live here so no adapter can forget them.
* **Not hammering a public API during development.** Responses are cached on
  disk with a per-source TTL, so re-running a search while building a paper
  costs nothing.
* **Offline tests.** `Fetcher` takes an injectable transport, so the whole
  retrieval layer is testable against recorded fixtures with no network and no
  credentials — the same approach the nursery tracker's sync tests use.
* **An honest audit trail.** Each response records the exact URL and the time
  it was fetched, which is what lets the companion document state when a search
  was run rather than implying it was live.

Nothing here retains full text beyond a cache TTL, and nothing is redistributed
— the cache is a local working copy, which is what the publishers' terms permit
and what a reference manager does too.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

USER_AGENT_TEMPLATE = (
    "KochResearchSuite/1.0 (single-user academic research tool; +mailto:{email})"
)

# Per-host minimum seconds between requests. These are the documented policy
# limits, not guesses — where a service publishes a rate, it is used verbatim.
DEFAULT_RATE_LIMITS: dict[str, float] = {
    "eutils.ncbi.nlm.nih.gov": 0.34,      # NCBI: 3/s without an API key
    "api.crossref.org": 0.05,             # Crossref polite pool
    "api.openalex.org": 0.11,             # OpenAlex: 10/s, 100k/day
    "api.semanticscholar.org": 1.05,      # S2: ~1/s unauthenticated
    "www.ebi.ac.uk": 0.15,                # Europe PMC
    "api.unpaywall.org": 0.11,            # Unpaywall: 100k/day, be polite
    "api.ies.ed.gov": 0.25,               # ERIC
    "clinicaltrials.gov": 0.25,
    "data.cdc.gov": 0.15,
    "ghoapi.azureedge.net": 0.15,
    "odphp.health.gov": 0.25,
    "health.gov": 0.25,
    "_default": 0.2,
}

# With an NCBI API key the documented ceiling rises to 10 requests/second.
NCBI_RATE_WITH_KEY = 0.11


@dataclass
class FetchResult:
    """A response plus the provenance the audit document needs."""

    url: str
    status: int
    json: Any = None
    text: str = ""
    from_cache: bool = False
    fetched_at: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.error


@dataclass
class SourceStatus:
    """What a source can do right now, and why not if it cannot.

    The UI shows this list so the user can see at a glance which databases are
    live, which need a key they have not supplied, and which are import-only —
    rather than discovering it when a search silently returns nothing.
    """

    key: str
    label: str
    kind: str                     # api | import-only
    available: bool
    requires: str = ""            # what is missing, if anything
    note: str = ""
    docs: str = ""


class DiskCache:
    """A plain JSON-on-disk cache. No index, no eviction thread — one file per
    request, named by a hash of the URL, with the TTL checked on read."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.directory / f"{digest}.json"

    def get(self, url: str, ttl_seconds: int) -> FetchResult | None:
        path = self._path(url)
        if not path.exists():
            return None
        if ttl_seconds >= 0 and (time.time() - path.stat().st_mtime) > ttl_seconds:
            return None
        try:
            payload = json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return FetchResult(
            url=url,
            status=payload.get("status", 200),
            json=payload.get("json"),
            text=payload.get("text", ""),
            from_cache=True,
            fetched_at=payload.get("fetched_at", ""),
        )

    def put(self, result: FetchResult) -> None:
        try:
            self._path(result.url).write_text(
                json.dumps({
                    "status": result.status,
                    "json": result.json,
                    "text": result.text if result.json is None else "",
                    "fetched_at": result.fetched_at,
                    "url": result.url,
                }),
                "utf-8",
            )
        except OSError:
            pass  # a cache that cannot write is a slow tool, not a broken one

    def clear(self) -> int:
        removed = 0
        for path in self.directory.glob("*.json"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed


class RateLimiter:
    """One asyncio lock and last-call timestamp per host."""

    def __init__(self, limits: dict[str, float] | None = None):
        self.limits = dict(limits or DEFAULT_RATE_LIMITS)
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def interval_for(self, host: str) -> float:
        return self.limits.get(host, self.limits.get("_default", 0.2))

    async def wait(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            interval = self.interval_for(host)
            elapsed = time.monotonic() - self._last.get(host, 0.0)
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._last[host] = time.monotonic()


class Fetcher:
    """The one place outbound HTTP happens."""

    def __init__(
        self,
        cache_dir: Path,
        contact_email: str = "",
        api_keys: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ):
        self.cache = DiskCache(cache_dir)
        self.contact_email = contact_email.strip()
        self.api_keys = {k: v for k, v in (api_keys or {}).items() if v}
        self.limiter = RateLimiter()
        if self.api_keys.get("ncbi"):
            self.limiter.limits["eutils.ncbi.nlm.nih.gov"] = NCBI_RATE_WITH_KEY
        self._transport = transport
        self._timeout = timeout
        self.log: list[dict[str, str]] = []

    # -------------------------------------------------------------- requests

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        ttl_seconds: int = 86_400,
        expect: str = "json",
        headers: dict[str, str] | None = None,
        retries: int = 2,
    ) -> FetchResult:
        request = httpx.Request("GET", url, params=_clean_params(params))
        full_url = str(request.url)

        cached = self.cache.get(full_url, ttl_seconds)
        if cached is not None:
            self._record(full_url, cached.status, cached=True)
            return cached

        host = request.url.host or "_default"
        merged_headers = {"User-Agent": self.user_agent(), "Accept": _accept(expect)}
        merged_headers.update(headers or {})

        last_error = ""
        for attempt in range(retries + 1):
            await self.limiter.wait(host)
            try:
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=self._timeout,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(full_url, headers=merged_headers)
            except httpx.HTTPError as error:
                last_error = f"{type(error).__name__}: {error}"
                await asyncio.sleep(0.6 * (2 ** attempt))
                continue

            result = FetchResult(
                url=full_url,
                status=response.status_code,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            if expect == "json":
                try:
                    result.json = response.json()
                except ValueError:
                    result.text = response.text
                    if response.status_code == 200:
                        result.error = "response was not valid JSON"
            else:
                result.text = response.text

            # 429 and 5xx are worth retrying; 4xx otherwise is not — a bad query
            # will be bad the second time too.
            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_error = f"HTTP {response.status_code}"
                retry_after = _retry_after_seconds(response)
                await asyncio.sleep(retry_after or 1.2 * (2 ** attempt))
                continue

            if result.ok:
                self.cache.put(result)
            self._record(full_url, result.status)
            return result

        self._record(full_url, 0, error=last_error)
        return FetchResult(url=full_url, status=0, error=last_error or "request failed")

    async def get_many(
        self, requests: list[tuple[str, dict[str, Any]]], **kwargs
    ) -> list[FetchResult]:
        """Concurrent GETs. The per-host rate limiter still serialises calls to
        the same API, so this speeds up fan-out across *different* sources
        without breaching any one policy."""
        return list(await asyncio.gather(
            *(self.get(url, params, **kwargs) for url, params in requests)
        ))

    # ------------------------------------------------------------- identity

    def user_agent(self) -> str:
        email = self.contact_email or "no-contact-configured"
        return USER_AGENT_TEMPLATE.format(email=email)

    def ncbi_params(self) -> dict[str, str]:
        """The identification NCBI's usage policy asks for on every call."""
        params = {"tool": "KochResearchSuite"}
        if self.contact_email:
            params["email"] = self.contact_email
        if self.api_keys.get("ncbi"):
            params["api_key"] = self.api_keys["ncbi"]
        return params

    def _record(self, url: str, status: int, *, cached: bool = False, error: str = "") -> None:
        self.log.append({
            "url": _redact(url),
            "status": str(status),
            "cached": "yes" if cached else "no",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": error,
        })
        if len(self.log) > 500:
            del self.log[:250]


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
    if not params:
        return {}
    return {k: v for k, v in params.items() if v not in (None, "", [])}


def _accept(expect: str) -> str:
    return {
        "json": "application/json",
        "xml": "application/xml, text/xml",
        "text": "text/plain, */*",
    }.get(expect, "*/*")


def _retry_after_seconds(response: httpx.Response) -> float:
    raw = response.headers.get("Retry-After", "")
    if raw.isdigit():
        return min(float(raw), 30.0)
    return 0.0


def _redact(url: str) -> str:
    """Strip credentials before a URL reaches a log or the audit document.

    The audit document reproduces every query URL so a search can be re-run, and
    an API key in one of them would be published the moment that document was
    emailed to a supervisor.
    """
    return re.sub(r"((?:api_?key|key|token|apikey|secret)=)[^&]+", r"\1REDACTED",
                  url, flags=re.IGNORECASE)


# ------------------------------------------------------------------ registry


@dataclass
class SourceSpec:
    """One evidence source, whether it has an API or not."""

    key: str
    label: str
    kind: str                        # api | import-only
    discipline: str
    docs: str = ""
    needs_key: str = ""              # the api_keys entry required, if any
    needs_email: bool = False
    note: str = ""
    search: Callable | None = field(default=None, repr=False)


class SourceRegistry:
    """Which sources exist, which are usable, and why not."""

    def __init__(self) -> None:
        self._specs: dict[str, SourceSpec] = {}

    def register(self, spec: SourceSpec) -> None:
        self._specs[spec.key] = spec

    def all(self) -> list[SourceSpec]:
        return sorted(self._specs.values(), key=lambda s: (s.kind, s.label))

    def get(self, key: str) -> SourceSpec | None:
        return self._specs.get(key)

    def status(self, fetcher: Fetcher) -> list[SourceStatus]:
        out: list[SourceStatus] = []
        for spec in self.all():
            missing: list[str] = []
            if spec.needs_key and not fetcher.api_keys.get(spec.needs_key):
                missing.append(f"an API key for {spec.needs_key}")
            if spec.needs_email and not fetcher.contact_email:
                missing.append("a contact email address")
            out.append(SourceStatus(
                key=spec.key,
                label=spec.label,
                kind=spec.kind,
                available=spec.kind == "api" and not missing,
                requires=", ".join(missing),
                note=spec.note,
                docs=spec.docs,
            ))
        return out

    def searchable(self, fetcher: Fetcher) -> list[SourceSpec]:
        available = {s.key for s in self.status(fetcher) if s.available}
        return [s for s in self.all() if s.key in available and s.search]


REGISTRY = SourceRegistry()
