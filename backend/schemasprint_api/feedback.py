"""Strict validation for provider-generated feedback envelopes.

The provider adapter returns untrusted text.  This module deliberately has no
database or network access; callers must validate before persistence.
"""

from __future__ import annotations

import json
from collections.abc import Collection

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class FeedbackOutputError(ValueError):
    """Raised when a provider response is not an acceptable feedback envelope."""


class FeedbackGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contentEn: str = Field(min_length=1, max_length=12_000)
    mentionedRequirementIds: list[str] = Field(default_factory=list, max_length=100)


def parse_feedback_output(
    raw: str, *, allowed_requirement_ids: Collection[str]
) -> FeedbackGeneration:
    """Parse JSON-only output and reject references outside the saved rubric."""
    try:
        parsed = json.loads(raw)
        output = FeedbackGeneration.model_validate(parsed)
    except (json.JSONDecodeError, TypeError, ValidationError) as error:
        raise FeedbackOutputError("LLM_INVALID_OUTPUT") from error
    allowed = set(allowed_requirement_ids)
    if any(item not in allowed for item in output.mentionedRequirementIds):
        raise FeedbackOutputError("LLM_INVALID_OUTPUT")
    return output
