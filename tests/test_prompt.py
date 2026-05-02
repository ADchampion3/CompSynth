from comp_synth.prompt import (
    DEFAULT_TAG_VOCABULARY,
    _sanitize_tags,
    build_summary_prompt,
)


def test_build_summary_prompt_with_custom_tags():
    prompt = build_summary_prompt(tags=["AI", "security"])
    assert "AI" in prompt
    assert "security" in prompt


def test_build_summary_prompt_falls_back_to_default():
    prompt = build_summary_prompt()
    for tag in DEFAULT_TAG_VOCABULARY:
        assert tag in prompt


def test_sanitize_strips_newlines():
    assert _sanitize_tags(["tag\nwith\nnewlines"]) == ["tagwithnewlines"]


def test_sanitize_strips_control_chars():
    assert _sanitize_tags(["tag\x00with\x01ctrl"]) == ["tagwithctrl"]


def test_sanitize_caps_at_30():
    tags = [f"tag{i}" for i in range(50)]
    result = _sanitize_tags(tags)
    assert len(result) == 30


def test_sanitize_skips_empty():
    assert _sanitize_tags(["", "valid", "   "]) == ["valid"]
