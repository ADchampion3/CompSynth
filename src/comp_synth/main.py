import argparse
import asyncio


async def run() -> dict:
    from comp_synth.orchestration.pipeline import run_pipeline
    from comp_synth.utils.logging import logger

    logger.info("CompSynth starting")

    result = await run_pipeline()

    if result.get("errors"):
        for err in result["errors"]:
            logger.warning(f"Pipeline error: {err}")

    status = result.get("publish_results", {}).get("status", "unknown")
    if status == "skipped":
        logger.info("No new content; exiting.")
    elif status == "success":
        path = result["publish_results"].get("path", "")
        logger.info(f"Digest written: {path}")
    else:
        logger.warning(f"Pipeline finished with status: {status}")

    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="compsynth",
        description="Run the CompSynth content aggregation pipeline.",
    )
    parser.parse_args(argv)
    asyncio.run(run())


if __name__ == "__main__":
    main()
