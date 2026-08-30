"""Thin wrapper over ChatOllama that returns Pydantic-parsed structured output.

Every LLM node calls `structured_output(schema, system=..., user=...)` — the
node stays declarative and the wrapper owns model wiring, structured-output
mode, and Ollama-specific quirks. Tests monkeypatch this module attribute
directly (see conftest.py) so the graph never hits the real model in unit
tests.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from pipeline_watch.config import settings

_llm: ChatOllama | None = None


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_host,
            temperature=settings.ollama_temperature,
        )
    return _llm


def structured_output[T: BaseModel](schema: type[T], *, system: str, user: str) -> T:
    """Invoke the LLM constrained to `schema`. Returns a parsed instance.

    Ollama's json-schema grammar path can reject certain schemas at compile
    time (`ResponseError: failed to parse grammar`). Callers should either
    keep their schema simple or wrap this call in try/except and treat the
    failure as "no result" — see `nodes/propose_patch.py` for the pattern.
    """

    structured = _get_llm().with_structured_output(schema)
    result = structured.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    if not isinstance(result, schema):
        raise TypeError(
            f"LLM returned {type(result).__name__}, expected {schema.__name__}"
        )
    return result


def reset_cache() -> None:
    """Used by tests that want a fresh ChatOllama with new settings."""

    global _llm
    _llm = None
