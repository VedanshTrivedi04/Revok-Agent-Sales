"""AI service settings. Environment only; no secrets in code."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = "dev-llm-key"
    llm_model: str = "Qwen/Qwen3.5-9B"
    llm_structured_mode: Literal["guided_json", "structured_outputs", "response_format", "none"] = (
        "response_format"
    )
    llm_enable_thinking: bool = False
    # Qwen3.5 thinks unless told not to, so the flag is sent on every call. Turn this off only for
    # a server that rejects `chat_template_kwargs`.
    llm_send_thinking_flag: bool = True
    llm_timeout_s: float = 120.0

    # Embeddings for Riddhi's retrieval index: any OpenAI-compatible /embeddings endpoint that is
    # self-hosted (Ollama, llama.cpp, TEI, vLLM). The backend's index stores 768 numbers per
    # passage, so the model must produce exactly that many.
    # 127.0.0.1, not localhost: on Windows a name lookup that tries IPv6 first costs ~2 s per call
    embed_base_url: str = "http://127.0.0.1:11434/v1"
    embed_api_key: str = "local"
    embed_model: str = "embeddinggemma"
    embed_dim: int = 768
    # EmbeddingGemma is trained with these task prefixes; leave both empty for a model without.
    embed_query_prefix: str = "task: search result | query: "
    embed_doc_prefix: str = "title: none | text: "

    internal_api_url: str = "http://localhost:8000/internal"
    internal_api_key: str = "dev-internal-key"

    # service (revops_ai.main)
    ai_service_key: str = ""  # X-AI-Key expected from the backend; empty = same as INTERNAL_API_KEY
    ai_max_concurrent_runs: int = 4  # runs in flight at once (bounded by the GPU, not by this box)
    ai_wait_for_approval: bool = False  # true = a run stays open until its tier-2 cards are decided
    checkpoint_dsn: str = ""  # postgres DSN for LangGraph checkpoints; empty = in memory

    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
