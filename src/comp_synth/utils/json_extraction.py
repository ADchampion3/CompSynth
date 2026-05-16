"""Shared utilities for extracting JSON from LLM output."""

import re

_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> str | None:
    """Extract a JSON string from LLM output (array or object).

    Handles markdown code-block wrapping and plain-text mixed output.
    """
    if "```" in text:
        for part in text.split("```")[1:]:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith(("{", "[")):
                return candidate
    m = _ARRAY_RE.search(text)
    if m:
        return m.group(0)
    m = _OBJECT_RE.search(text)
    return m.group(0) if m else None


def coerce_text_content(content: str | list) -> str:
    """Normalize LLM response content to a plain string.

    Some providers return a list of content blocks instead of a string.
    """
    if isinstance(content, list):
        return "".join(
            block["text"] for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return content
