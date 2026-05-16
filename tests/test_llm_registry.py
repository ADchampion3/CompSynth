import pytest

from comp_synth.crawlers.extractors import DOMExtractor
from comp_synth.llm_provider.registry import LLMConfigurationError, LLMRegistry


def test_missing_llm_provider_error_names_required_env_vars():
    registry = LLMRegistry({"model": "gpt-4o-mini"})

    with pytest.raises(LLMConfigurationError) as exc:
        registry.get("gpt-4o-mini")

    message = str(exc.value)
    assert "COMPSYNTH_OPENAI_API_KEY" in message
    assert "COMPSYNTH_ANTHROPIC_API_KEY" in message


def test_dom_extractor_does_not_load_llm_until_llm_method(monkeypatch):
    def fail_get(*args, **kwargs):
        raise AssertionError("LLM should not be loaded for selector extraction")

    monkeypatch.setattr("comp_synth.crawlers.extractors._llm_registry.llm_registry.get", fail_get)

    extractor = DOMExtractor()
    html = "<article><a href='/a'><h2>Title</h2></a><p>Summary</p></article>"
    items = extractor.extract_list_items_with_selectors(
        html,
        [{"item_container": "article", "url": "a", "title": "h2", "summary": "p"}],
    )

    assert items[0]["title"] == "Title"
