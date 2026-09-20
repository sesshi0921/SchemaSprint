from __future__ import annotations

import httpx
import pytest
import respx
from schemasprint_api.jev import JevClient, JevError


@pytest.mark.asyncio
@respx.mock
async def test_system_one_request_is_typed_and_redacted() -> None:
    route = respx.post("https://jev.example/v1/systemone").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "rubric_x": {"type": "noul", "noul": 0.9},
                },
                "usage": {"input_tokens": 12, "output_tokens": 3},
            },
        )
    )
    client = JevClient("https://jev.example", "secret-key", max_retries=0)

    result = await client.assess(
        state={"candidateSchema": {"tables": []}},
        questions={
            "rubric_x": {
                "type": "noul",
                "instructions": "Does the schema satisfy the requirement?",
                "criteria": {"true": "yes", "false": "no"},
            }
        },
    )

    assert result.model == "jev-1.13.0"
    assert result.decisions["rubric_x"].satisfied
    assert result.decisions["rubric_x"].confidence == pytest.approx(80)
    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer secret-key"
    body = request.content.decode("utf-8")
    assert "candidateSchema" in body
    assert "user_id" not in body
    assert "secret-key" not in body


@pytest.mark.asyncio
@respx.mock
async def test_system_one_retries_rate_limit_once() -> None:
    route = respx.post("https://jev.example/v1/systemone").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(
                200,
                json={
                    "model": "jev-latest",
                    "answers": {"q": {"type": "noul", "noul": 0.1}},
                },
            ),
        ]
    )
    client = JevClient("https://jev.example", "key", max_retries=1)
    result = await client.assess(
        state="schema",
        questions={"q": {"type": "noul", "instructions": "Is it valid?"}},
    )
    assert not result.decisions["q"].satisfied
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_invalid_response_is_rejected_without_fabricating_a_decision() -> None:
    respx.post("https://jev.example/v1/systemone").mock(
        return_value=httpx.Response(
            200,
            json={"model": "jev-latest", "answers": {}},
        )
    )
    client = JevClient("https://jev.example", "key", max_retries=0)
    with pytest.raises(JevError, match="JEV_RESPONSE_INVALID"):
        await client.assess(
            state="schema",
            questions={"q": {"type": "noul", "instructions": "Is it valid?"}},
        )


@pytest.mark.asyncio
@respx.mock
async def test_auth_failure_is_not_retried() -> None:
    route = respx.post("https://jev.example/v1/systemone").mock(
        return_value=httpx.Response(401)
    )
    client = JevClient("https://jev.example", "key", max_retries=3)
    with pytest.raises(JevError, match="JEV_AUTH_FAILED"):
        await client.assess(
            state="schema",
            questions={"q": {"type": "noul", "instructions": "Is it valid?"}},
        )
    assert route.call_count == 1
