from langchain_core.language_models import BaseChatModel


class LLMRegistry:
    """LLM 注册表，管理多个 LLM provider 实例"""

    def __init__(self, config: dict):
        self._providers: dict[str, BaseChatModel] = {}
        self._init_llm(config)

    def _init_llm(self, config: dict):
        if config.get("openai_api_key", "") != "" and config.get("openai_base_url", "") != "" and config.get("model", "") != "":
            openai_api_key = config["openai_api_key"]
            openai_base_url = config["openai_base_url"]
            model_name = config["model"]
            self._register(model_name, {"type": "openai", "api_key": openai_api_key, "base_url": openai_base_url, "model": model_name})

        if config.get("anthropic_api_key", "") != "" and config.get("anthropic_base_url", "") != "" and config.get("model",
                                                                                                             "") != "":
            anthropic_api_key = config["anthropic_api_key"]
            anthropic_base_url = config["anthropic_base_url"]
            model_name = config["model"]
            self._register(model_name, {"type": "anthropic", "api_key": anthropic_api_key, "base_url": anthropic_base_url,
                                       "model": model_name})


    def _register(self, name: str, provider_config: dict) -> None:
        """
        注册一个 LLM provider

        Args:
            name: provider 名称标识
            provider_config: provider 配置，包含 type, model, api_key 等
        """
        self._providers[name] = self._create_provider(provider_config)

    def get(self, name: str) -> BaseChatModel:
        """获取已注册的 provider 实例"""
        if name not in self._providers:
            raise KeyError(f"LLM provider '{name}' 未注册")
        return self._providers[name]

    def list_providers(self) -> list[str]:
        """列出所有已注册的 provider 名称"""
        return list(self._providers.keys())

    def _create_provider(self, config: dict) -> BaseChatModel:
        """
        根据配置创建 LLM provider 实例

        Args:
            config: provider 配置
                - type: "openai" | "anthropic"
                - model: 模型名称
                - api_key: API 密钥
                - base_url: (可选) 自定义 API 地址

        Returns:
            BaseChatModel 实例
        """
        provider_type = config["type"]

        if provider_type == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=config.get("model", "gpt-4o-mini"),
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url"),
            )
        elif provider_type == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=config.get("model", "claude-sonnet-4-20250514"),
                api_key=config.get("api_key", ""),
            )
        else:
            raise ValueError(f"不支持的 provider 类型: {provider_type}")
