import os

from dotenv import load_dotenv

from comp_synth.llm import LLMRegistry

load_dotenv()

llm_config = {
    "openai_base_url": "https://api.siliconflow.cn/v1",
    "openai_api_key": os.environ.get("COMPSYNTH_OPENAI_API_KEY"),
"model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
}

def test_openai_api():
    global llm_config
    llm_registry = LLMRegistry(llm_config)
    llm = llm_registry.get(llm_config["model"])
    llm.invoke("hello").pretty_print()
