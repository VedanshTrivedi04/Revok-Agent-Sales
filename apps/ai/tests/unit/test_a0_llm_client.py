import json
import os
from pathlib import Path

import pytest

from revops_ai.config import Settings
from revops_ai.llm.client import (
    FakeLLM,
    LLMOutputError,
    OpenAICompatClient,
    strip_json,
    structured_kwargs,
)
from revops_ai.llm.schemas import DraftOutput, ExplainOutput, ExtractOutput
from tests.fake_llm_server import FakeLLMServer

BASE = "http://llm.test/v1"


def _settings(**kw: object) -> Settings:
    kw.setdefault("llm_base_url", BASE)
    return Settings(llm_api_key="k", _env_file=None, **kw)  # type: ignore[call-arg]


def test_strip_json_handles_fences_and_think_blocks() -> None:
    assert json.loads(strip_json('```json\n{"a": 1}\n```')) == {"a": 1}
    assert json.loads(strip_json('<think>hmm {x}</think>\n{"a": 2}')) == {"a": 2}


def test_structured_kwargs_per_mode() -> None:
    assert (
        "guided_json"
        in structured_kwargs(_settings(llm_structured_mode="guided_json"), ExtractOutput)[
            "extra_body"
        ]
    )
    assert (
        "structured_outputs"
        in structured_kwargs(_settings(llm_structured_mode="structured_outputs"), ExtractOutput)[
            "extra_body"
        ]
    )
    rf = structured_kwargs(_settings(llm_structured_mode="response_format"), ExtractOutput)
    assert rf["response_format"]["type"] == "json_schema"
    assert structured_kwargs(_settings(llm_structured_mode="none"), ExtractOutput) == {}


async def test_call_json_parses_and_never_sends_tools(llm_server: FakeLLMServer) -> None:
    llm_server.push(
        '{"signals": [{"kind":"sentiment","polarity":"negative","value":null,"quote":"bad","confidence":0.9}]}'
    )
    c = OpenAICompatClient(_settings(llm_base_url=llm_server.base_url))
    out, meta = await c.call_json("extract", [{"role": "user", "content": "hi"}], ExtractOutput)
    assert out.signals[0].kind == "sentiment"
    assert meta.prompt_tokens == 11 and meta.completion_tokens == 7
    body = llm_server.requests[0]
    assert "tools" not in body and "functions" not in body and "tool_choice" not in body
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["response_format"]["type"] == "json_schema"


async def test_invalid_json_raises_llm_output_error(llm_server: FakeLLMServer) -> None:
    llm_server.push("not json at all")
    c = OpenAICompatClient(_settings(llm_base_url=llm_server.base_url))
    with pytest.raises(LLMOutputError):
        await c.call_json("extract", [{"role": "user", "content": "x"}], ExtractOutput)


async def test_schema_violation_raises_llm_output_error(llm_server: FakeLLMServer) -> None:
    llm_server.push(
        '{"summary":"s","claims":[{"text":"t","evidence_ids":["bad"]}],"unknowns":[],"contradictions":[],"confidence":"strong"}'
    )
    c = OpenAICompatClient(_settings(llm_base_url=llm_server.base_url))
    with pytest.raises(LLMOutputError):
        await c.call_json("explain", [{"role": "user", "content": "x"}], ExplainOutput)


async def test_retries_on_5xx_then_succeeds(llm_server: FakeLLMServer) -> None:
    llm_server.push(status=503)
    llm_server.push('{"signals": []}')
    c = OpenAICompatClient(_settings(llm_base_url=llm_server.base_url))
    out, _ = await c.call_json("extract", [{"role": "user", "content": "x"}], ExtractOutput)
    assert out.signals == [] and len(llm_server.requests) == 2


async def test_fake_llm_queue_and_record_replay(tmp_path: Path) -> None:
    fake = FakeLLM([{"signals": []}], recorded_dir=tmp_path)
    out, _ = await fake.call_json("extract", [{"role": "user", "content": "x"}], ExtractOutput)
    assert out.signals == []
    with pytest.raises(LLMOutputError):
        await fake.call_json("extract", [{"role": "user", "content": "y"}], ExtractOutput)


async def test_fake_llm_records_from_real_then_replays(tmp_path: Path) -> None:
    real = FakeLLM([{"signals": []}])
    rec = FakeLLM(recorded_dir=tmp_path, record_with=real)
    msgs = [{"role": "user", "content": "z"}]
    await rec.call_json("extract", msgs, ExtractOutput)
    assert len(os.listdir(tmp_path)) == 1
    replay = FakeLLM(recorded_dir=tmp_path)
    out, _ = await replay.call_json("extract", msgs, ExtractOutput)
    assert out.signals == []


def test_schemas_enforce_limits() -> None:
    with pytest.raises(ValueError):
        ExplainOutput.model_validate(
            {
                "summary": "s",
                "claims": [],
                "unknowns": [],
                "contradictions": [],
                "confidence": "weak",
            }
        )
    d = DraftOutput.model_validate(
        {"actions": [{"type": "crm_task", "title": "t", "body": "b", "due_in_days": 2,
                      "priority": "HIGH", "rationale": "r", "evidence_ids": ["E1"]}]}
    )  # fmt: skip
    assert d.actions[0].type == "crm_task"
    with pytest.raises(ValueError):
        DraftOutput.model_validate({"actions": [{"type": "refund", "evidence_ids": ["E1"]}]})
