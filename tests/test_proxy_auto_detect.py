"""Tests for proxy auto-detection logic in ContentManager."""

from comp_synth.orchestration.content_manager import ContentManager


def test_is_proxy_trigger_error_detects_timeout():
    assert ContentManager._is_proxy_trigger_error("Connection timeout after 30s") is True


def test_is_proxy_trigger_error_detects_403():
    assert ContentManager._is_proxy_trigger_error("HTTP 403 Forbidden") is True


def test_is_proxy_trigger_error_detects_cloudflare():
    assert ContentManager._is_proxy_trigger_error("Cloudflare challenge page") is True


def test_is_proxy_trigger_error_detects_429():
    assert ContentManager._is_proxy_trigger_error("429 Too Many Requests") is True


def test_is_proxy_trigger_error_ignores_parse_error():
    assert ContentManager._is_proxy_trigger_error("Failed to parse JSON response") is False


def test_is_proxy_trigger_error_ignores_empty():
    assert ContentManager._is_proxy_trigger_error("") is False


def test_is_proxy_trigger_error_case_insensitive():
    assert ContentManager._is_proxy_trigger_error("SSL Certificate Error") is True
    assert ContentManager._is_proxy_trigger_error("CONNECTION REFUSED") is True
