import asyncio

from comp_synth.config import settings  # noqa: F401 - 触发config读取
from comp_synth.llm_provider.registry import llm_registry  # noqa: F401 - 触发registry加载
from comp_synth.orchestration.graph import build_pipeline
from comp_synth.utils.logging import logger  # 触发日志配置


async def run():
    logger.info("CompSynth 启动")


    pipeline = build_pipeline()
    result = await pipeline.ainvoke({
        "sources": [],
        "raw_items": [],
        "new_items": [],
        "topic_groups": [],
        "report": "",
        "publish_results": {},
        "errors": [],
    })

    if result.get("errors"):
        for err in result["errors"]:
            logger.warning(f"管线错误: {err}")

    status = result.get("publish_results", {}).get("status", "unknown")
    if status == "skipped":
        logger.info("没有新内容，退出。")
    elif status == "success":
        path = result["publish_results"].get("path", "")
        logger.info(f"摘要已生成: {path}")
    else:
        logger.warning(f"管线结束，状态: {status}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
