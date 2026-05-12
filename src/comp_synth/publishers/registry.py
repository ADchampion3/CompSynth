from comp_synth.publishers.base import BasePublisher

_PUBLISHERS: dict[str, type[BasePublisher]] = {}


def _load_publishers() -> None:
    if _PUBLISHERS:
        return
    from comp_synth.publishers.email import EmailPublisher

    _PUBLISHERS["email"] = EmailPublisher


def reset_registry() -> None:
    _PUBLISHERS.clear()


def get_enabled_publishers(channels: list[str]) -> list[BasePublisher]:
    _load_publishers()
    result: list[BasePublisher] = []
    for ch in channels:
        cls = _PUBLISHERS.get(ch)
        if cls:
            result.append(cls())
    return result
