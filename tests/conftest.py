import pytest


@pytest.fixture(autouse=True)
def block_real_llm_calls_by_default(request, monkeypatch):
    """Keep unit tests deterministic unless they explicitly opt into real LLM calls."""
    if request.node.get_closest_marker("allow_llm"):
        return

    def fail_get(*args, **kwargs):
        raise AssertionError(
            "Real LLM provider access is disabled in tests. "
            "Mock llm_registry.get or mark the test with @pytest.mark.allow_llm."
        )

    monkeypatch.setattr("comp_synth.llm_provider.registry.llm_registry.get", fail_get)
