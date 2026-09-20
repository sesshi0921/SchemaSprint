"""Small, bounded HTTP controls for the private BFF service.

The Cloudflare Worker remains the public edge and must enforce its own WAF,
body, concurrency, and distributed rate limits.  This module is a defence in
depth layer for a single Python container; it deliberately does not trust
forwarded client addresses unless the immediate peer is configured as a
trusted proxy.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address
from typing import Final

from fastapi import Request

from .security import token_digest

UNSAFE_METHODS: Final[frozenset[str]] = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_CONTENT_LENGTH = re.compile(r"^[0-9]+$")
_MAX_IP_HEADER_LENGTH: Final = 64


class RequestBodyTooLarge(Exception):
    """Raised by the receive wrapper once a streamed body exceeds its bound."""


class InvalidContentLength(Exception):
    """Raised when a request advertises a malformed content length."""


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class InProcessRateLimiter:
    """A bounded async token-bucket limiter for one service instance.

    The map is an LRU cache with a fixed upper bound.  A new key evicts the
    least-recently-used bucket instead of causing a global denial when an
    attacker sprays unique keys.  The edge/IP-wide limiter remains the
    protection against cookie/key rotation; this process-local cache only
    provides bounded per-key accounting.
    """

    def __init__(
        self,
        capacity: int,
        window_seconds: int,
        max_keys: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity < 1 or window_seconds < 1 or max_keys < 1:
            raise ValueError("invalid rate limiter bounds")
        self.capacity = capacity
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._lock = asyncio.Lock()

    @property
    def key_count(self) -> int:
        return len(self._buckets)

    async def check(self, key: str) -> RateLimitDecision:
        now = self._clock()
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self.max_keys:
                    # OrderedDict.popitem is O(1) amortized and keeps the
                    # memory bound independent of attacker-controlled keys.
                    self._buckets.popitem(last=False)
                bucket = _Bucket(float(self.capacity), now)
                self._buckets[key] = bucket
            else:
                elapsed = max(0.0, now - bucket.updated_at)
                bucket.tokens = min(
                    float(self.capacity),
                    bucket.tokens + elapsed * self.capacity / self.window_seconds,
                )
                bucket.updated_at = now
                self._buckets.move_to_end(key)

            if bucket.tokens < 1.0:
                wait = (1.0 - bucket.tokens) * self.window_seconds / self.capacity
                return RateLimitDecision(False, 0, max(1, int(wait + 0.999)))
            bucket.tokens -= 1.0
            return RateLimitDecision(True, int(bucket.tokens), 0)


def parse_content_length(value: str | None) -> int | None:
    """Parse one non-negative decimal Content-Length without integer surprises."""

    if value is None:
        return None
    if not _CONTENT_LENGTH.fullmatch(value.strip()):
        raise InvalidContentLength
    return int(value, 10)


def _peer_address(request: Request) -> IPv4Address | IPv6Address | None:
    client = request.client
    if client is None:
        return None
    try:
        return ipaddress.ip_address(client.host)
    except ValueError:
        return None


def client_address(request: Request, trusted_proxy_cidrs: Iterable[str]) -> str:
    """Return a stable address, accepting CF-Connecting-IP only from trusted peers."""

    peer = _peer_address(request)
    trusted = False
    if peer is not None:
        for network_text in trusted_proxy_cidrs:
            try:
                if peer in ipaddress.ip_network(network_text, strict=False):
                    trusted = True
                    break
            except ValueError:
                # Settings validates these values; fail closed if called with
                # an unvalidated value rather than trusting a forwarded header.
                continue
    if trusted:
        forwarded = request.headers.get("CF-Connecting-IP", "").strip()
        if len(forwarded) <= _MAX_IP_HEADER_LENGTH and "," not in forwarded:
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
    return str(peer) if peer is not None else "unknown"


def request_source_key(
    request: Request, trusted_proxy_cidrs: Iterable[str], session_pepper: str
) -> str:
    """Build a non-secret source key combining address and an opaque session hash."""

    address = client_address(request, trusted_proxy_cidrs)
    token = request.cookies.get("__Host-schemasprint_session", "")
    if 32 <= len(token) <= 512:
        return f"{address}:session:{token_digest(token, session_pepper)[:32]}"
    return address


def same_origin(request: Request, allowed_origin: str) -> bool:
    """Require an exact Origin value; schemes/ports/trailing slash must match config."""

    origin = request.headers.get("Origin")
    if origin is None or len(origin) > 512:
        return False
    return origin == allowed_origin.rstrip("/")


def security_headers(*, production: bool) -> dict[str, str]:
    """Headers safe for JSON BFF responses; no inline/script capabilities."""

    headers = {
        "Content-Security-Policy": (
            "default-src 'none'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'"
        ),
        "Permissions-Policy": (
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        ),
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-Permitted-Cross-Domain-Policies": "none",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cache-Control": "no-store",
    }
    if production:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


__all__ = [
    "InvalidContentLength",
    "InProcessRateLimiter",
    "RateLimitDecision",
    "RequestBodyTooLarge",
    "UNSAFE_METHODS",
    "client_address",
    "parse_content_length",
    "request_source_key",
    "same_origin",
    "security_headers",
]
