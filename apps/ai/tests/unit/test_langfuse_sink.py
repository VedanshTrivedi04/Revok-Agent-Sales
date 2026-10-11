"""The Langfuse sink must use methods that exist in the installed SDK (it silently broke once when it did not)."""

from langfuse import Langfuse

from revops_ai.observability import tracing


def test_sdk_has_the_methods_the_sink_calls() -> None:
    assert hasattr(Langfuse, "start_as_current_observation")
    assert hasattr(Langfuse, "flush")


def test_sink_source_does_not_use_removed_span_api() -> None:
    import inspect

    src = inspect.getsource(tracing.LangfuseSink)
    assert "start_as_current_span" not in src
    assert "start_as_current_observation" in src


def test_mask_is_callable_with_langfuse_keyword_signature() -> None:
    # Langfuse calls mask(data=...) by keyword
    wrapper = lambda *, data, **_: tracing.mask(data)  # noqa: E731
    assert wrapper(data={"a": "x@y.example.com"}) == {"a": "[email]"}
