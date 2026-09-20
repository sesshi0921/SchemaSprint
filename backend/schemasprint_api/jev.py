"""Small, defensive HTTP client for the Jev System One endpoint.

The client intentionally knows only the provider's typed decision protocol.  It
does not accept an authenticated principal and never serialises application
session data.  Callers are responsible for building a redacted evaluation
state from server-owned snapshots before calling it.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_QUESTION_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_MAX_STATE_BYTES = 512 * 1024
_MAX_QUESTION_COUNT = 2_000
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504, 529})


class JevError(RuntimeError):
    """Safe provider failure; ``code`` is suitable for a public API error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _NoulAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["noul"]
    noul: float = Field(ge=0, le=1)


class _ChoiceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)


class _ScoreAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["score"]
    score: float
    legend: dict[str, str]
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)


JevAnswer = Annotated[
    _NoulAnswer | _ChoiceAnswer | _ScoreAnswer,
    Field(discriminator="type"),
]


class _Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class _Response(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=128)
    answers: dict[str, JevAnswer]
    usage: _Usage | None = None


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["noul"]
    instructions: str | Mapping[str, Any] | list[Any]
    criteria: dict[Literal["true", "false"], str] | None = None

    @field_validator("instructions")
    @classmethod
    def bounded_instructions(
        cls, value: str | Mapping[str, Any] | list[Any]
    ) -> str | Mapping[str, Any] | list[Any]:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 16 * 1024:
            raise ValueError("question instructions are too large")
        return value


@dataclass(frozen=True, slots=True)
class JevDecision:
    """A normalised Noul answer used by the scoring pipeline."""

    satisfied: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class JevAssessment:
    model: str
    decisions: dict[str, JevDecision]
    raw: dict[str, Any]


class JevClient:
    """Async System One client with bounded retries and response validation."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str = "jev-latest",
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url or not api_key or not model:
            raise ValueError("Jev credentials and model are required")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("Jev timeout must be between 0 and 30 seconds")
        if max_retries < 0 or max_retries > 3:
            raise ValueError("Jev retries must be between 0 and 3")
        endpoint = base_url.rstrip("/")
        if not endpoint.endswith("/v1/systemone"):
            endpoint += "/v1/systemone"
        self._endpoint = endpoint
        self._api_key = api_key
        self._model = model
        self._timeout = httpx.Timeout(timeout_seconds)
        self._max_retries = max_retries
        self._transport = transport

    async def assess(
        self,
        *,
        state: Mapping[str, Any] | str | list[Any],
        questions: Mapping[str, Mapping[str, Any]],
    ) -> JevAssessment:
        """Evaluate redacted state; never include identity or provider secrets."""
        if not questions or len(questions) > _MAX_QUESTION_COUNT:
            raise JevError("JEV_REQUEST_INVALID")
        normalized: dict[str, dict[str, Any]] = {}
        for key, value in questions.items():
            if not _QUESTION_ID.fullmatch(key):
                raise JevError("JEV_REQUEST_INVALID")
            try:
                normalized[key] = _Question.model_validate(value).model_dump(
                    mode="json", exclude_none=True
                )
            except ValidationError as error:
                raise JevError("JEV_REQUEST_INVALID") from error
        try:
            encoded_state = json.dumps(
                state, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise JevError("JEV_REQUEST_INVALID") from error
        if len(encoded_state) > _MAX_STATE_BYTES:
            raise JevError("JEV_REQUEST_TOO_LARGE")
        body = {"model": self._model, "state": state, "questions": normalized}
        try:
            encoded_body = json.dumps(
                body, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise JevError("JEV_REQUEST_INVALID") from error
        if len(encoded_body) > _MAX_STATE_BYTES:
            raise JevError("JEV_REQUEST_TOO_LARGE")
        response = await self._post(body)
        try:
            parsed = _Response.model_validate(response)
        except ValidationError as error:
            raise JevError("JEV_RESPONSE_INVALID") from error
        decisions: dict[str, JevDecision] = {}
        for key in questions:
            answer = parsed.answers.get(key)
            if not isinstance(answer, _NoulAnswer):
                raise JevError("JEV_RESPONSE_INVALID")
            probability = answer.noul
            decisions[key] = JevDecision(
                satisfied=probability >= 0.5,
                confidence=abs(probability - 0.5) * 200,
            )
        if set(parsed.answers) != set(questions):
            raise JevError("JEV_RESPONSE_INVALID")
        return JevAssessment(
            model=parsed.model,
            decisions=decisions,
            raw=parsed.model_dump(mode="json"),
        )

    async def _post(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as client:
                    response = await client.post(
                        self._endpoint, headers=headers, json=body
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt >= self._max_retries:
                    raise JevError("JEV_TIMEOUT") from error
                await asyncio.sleep(min(0.25 * 2**attempt, 1.0))
                continue
            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError as error:
                    raise JevError("JEV_RESPONSE_INVALID") from error
                if not isinstance(payload, Mapping):
                    raise JevError("JEV_RESPONSE_INVALID")
                return cast(Mapping[str, Any], payload)
            if response.status_code in {401, 403}:
                raise JevError("JEV_AUTH_FAILED")
            if response.status_code in {400, 422}:
                raise JevError("JEV_REQUEST_INVALID")
            if response.status_code not in _RETRYABLE_STATUS:
                raise JevError("JEV_UPSTREAM_UNAVAILABLE")
            if attempt >= self._max_retries:
                raise JevError("JEV_UPSTREAM_UNAVAILABLE")
            retry_after = response.headers.get("Retry-After")
            try:
                delay = min(float(retry_after or 0.25 * 2**attempt), 2.0)
            except ValueError:
                delay = min(0.25 * 2**attempt, 2.0)
            await asyncio.sleep(max(delay, 0.0))
        raise JevError("JEV_UPSTREAM_UNAVAILABLE")
