"""LLM client for the self-hosted Qwen3.5-9B behind an OpenAI-compatible server (vLLM).

Rules (agent.md): the model never gets tools, so no `tools`/`functions` parameter is ever sent.
Message content is never logged; only task name, sizes, latency and token counts.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypeVar

import structlog
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from revops_ai.config import Settings, get_settings

log = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)


class LLMOutputError(Exception):
    """The model answered but the output is not valid JSON for the schema."""


@dataclass(frozen=True)
class CallMeta:
    task: str
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    raw_chars: int


class LLMClient(Protocol):
    async def call_json(
        self,
        task: str,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> tuple[T, CallMeta]: ...


def structured_kwargs(settings: Settings, schema: type[BaseModel]) -> dict[str, Any]:
    """Request kwargs that force schema-valid JSON (adapt per vLLM version here)."""
    js = schema.model_json_schema()
    mode = settings.llm_structured_mode
    if mode == "guided_json":
        return {"extra_body": {"guided_json": js}}
    if mode == "structured_outputs":
        return {"extra_body": {"structured_outputs": {"json": js}}}
    if mode == "response_format":
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": js, "strict": True},
            }
        }
    return {}


def _extra_body(settings: Settings, kwargs: dict[str, Any]) -> dict[str, Any]:
    body = dict(kwargs.get("extra_body", {}))
    if settings.llm_send_thinking_flag:
        body["chat_template_kwargs"] = {"enable_thinking": settings.llm_enable_thinking}
    return body


def strip_json(text: str) -> str:
    """Tolerate ```json fences or a <think> block in front of the JSON."""
    t = text.strip()
    if "</think>" in t:
        t = t.split("</think>", 1)[1].strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t.lower().startswith("json") else t
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end > start else t


class OpenAICompatClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self.client = AsyncOpenAI(
            base_url=self.s.llm_base_url, api_key=self.s.llm_api_key, timeout=self.s.llm_timeout_s
        )

    async def call_json(
        self,
        task: str,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> tuple[T, CallMeta]:
        kwargs = structured_kwargs(self.s, schema)
        extra_body = _extra_body(self.s, kwargs)
        kwargs = {k: v for k, v in kwargs.items() if k != "extra_body"}
        t0 = time.perf_counter()
        resp = None
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(
                (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)
            ),
            stop=stop_after_attempt(4),
            wait=wait_exponential_jitter(multiplier=1, max=20),
            reraise=True,
        ):
            with attempt:
                create_kwargs: dict[str, Any] = {
                    "model": self.s.llm_model,
                    "messages": messages,  # type: ignore[arg-type]
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs,
                }
                if extra_body:
                    create_kwargs["extra_body"] = extra_body
                resp = await self.client.chat.completions.create(**create_kwargs)
        assert resp is not None
        text = resp.choices[0].message.content or ""
        latency = int((time.perf_counter() - t0) * 1000)
        usage = resp.usage
        meta = CallMeta(
            task, self.s.llm_model, latency,
            usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0, len(text),
        )  # fmt: skip
        log.info("llm_call", task=task, latency_ms=latency, tokens_out=meta.completion_tokens)
        try:
            return schema.model_validate_json(strip_json(text)), meta
        except (ValidationError, ValueError) as e:
            raise LLMOutputError(f"{task}: invalid output ({type(e).__name__})") from e


def _key(task: str, messages: list[dict[str, str]], schema: type[BaseModel]) -> str:
    raw = json.dumps([task, schema.__name__, messages], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class FakeLLM:
    """Deterministic LLM for tests and CI.

    Replays `tests/recorded/<key>.json` if present; otherwise returns the next queued response.
    With `record_to` set it wraps a real client and saves every answer (`--record`).
    """

    def __init__(
        self,
        responses: list[dict[str, Any] | str] | None = None,
        *,
        recorded_dir: Path | None = None,
        record_with: LLMClient | None = None,
    ) -> None:
        self.queue = list(responses or [])
        self.dir = recorded_dir
        self.real = record_with
        self.calls: list[dict[str, Any]] = []

    async def call_json(
        self,
        task: str,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> tuple[T, CallMeta]:
        self.calls.append({"task": task, "messages": messages, "temperature": temperature})
        key = _key(task, messages, schema)
        meta = CallMeta(task, "fake", 1, 0, 0, 0)
        if self.dir and (self.dir / f"{key}.json").exists():
            data = json.loads((self.dir / f"{key}.json").read_text(encoding="utf-8"))
            return schema.model_validate(data), meta
        if self.queue:
            item = self.queue.pop(0)
            text = item if isinstance(item, str) else json.dumps(item)
            try:
                return schema.model_validate_json(strip_json(text)), meta
            except (ValidationError, ValueError) as e:
                raise LLMOutputError(f"{task}: invalid output") from e
        if self.real is not None and self.dir is not None:
            out, real_meta = await self.real.call_json(
                task, messages, schema, temperature=temperature, max_tokens=max_tokens
            )
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / f"{key}.json").write_text(out.model_dump_json(indent=1), encoding="utf-8")
            return out, real_meta
        raise LLMOutputError(f"{task}: FakeLLM has no response for key {key}")
