from typing import Any

from langchain_core.language_models import BaseChatModel

from comp_synth.config import settings


class LLMConfigurationError(RuntimeError):
    """Raised when an LLM provider is requested but not configured."""


class LLMRegistry:
    """Registry for configured LangChain chat model providers."""

    def __init__(self, config: dict[str, Any]):
        self._providers: dict[str, BaseChatModel] = {}
        self._init_llm(config)

    def _init_llm(self, config: dict[str, Any]) -> None:
        model_name = config.get("model", "")
        if not model_name:
            return

        if config.get("openai_api_key") and config.get("openai_base_url"):
            self._register(
                model_name,
                {
                    "type": "openai",
                    "api_key": config["openai_api_key"],
                    "base_url": config["openai_base_url"],
                    "model": model_name,
                },
            )

        if config.get("anthropic_api_key"):
            self._register(
                model_name,
                {
                    "type": "anthropic",
                    "api_key": config["anthropic_api_key"],
                    "base_url": config.get("anthropic_base_url"),
                    "model": model_name,
                },
            )

    def _register(self, name: str, provider_config: dict[str, Any]) -> None:
        self._providers[name] = self._create_provider(provider_config)

    def get(self, name: str | None = None) -> BaseChatModel:
        provider_name = name or settings.model
        if provider_name not in self._providers:
            raise LLMConfigurationError(
                f"LLM provider '{provider_name}' is not configured. Set "
                "COMPSYNTH_OPENAI_API_KEY for OpenAI-compatible models or "
                "COMPSYNTH_ANTHROPIC_API_KEY for Anthropic models. "
                "Set COMPSYNTH_MODEL to the configured model name if needed."
            )
        return self._providers[provider_name]

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def _create_provider(self, config: dict[str, Any]) -> BaseChatModel:
        provider_type = config["type"]

        if provider_type == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=config.get("model", "gpt-4o-mini"),
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url"),
            )
        if provider_type == "anthropic":
            from langchain_anthropic import ChatAnthropic

            kwargs: dict[str, Any] = {
                "model": config.get("model", "claude-sonnet-4-20250514"),
                "api_key": config.get("api_key", ""),
            }
            if config.get("base_url"):
                kwargs["base_url"] = config["base_url"]
            return ChatAnthropic(**kwargs)

        raise ValueError(f"Unsupported provider type: {provider_type}")


llm_registry = LLMRegistry(settings.model_dump())
