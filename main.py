"""Cogentic AI daily content pipeline entry point."""

import os

from scheduler.daily_runner import run_daily_pipeline


def report_workflow_status(result: dict[str, object]) -> None:
    """Expose non-sensitive fallback status in GitHub Actions."""
    content_source = result.get("content_source")
    if not isinstance(content_source, str) or not content_source.startswith("csv_fallback"):
        return

    message = "CSV fallback content was published; review this workflow's logs."
    print(f"::warning title=Daily content fallback::{message}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## Daily content fallback\n\n")
            summary.write(f"{message}\n")


def main() -> None:
    """Run the daily content pipeline: theme, generation, evaluation, poster."""
    result = run_daily_pipeline()
    report_workflow_status(result)


if __name__ == "__main__":
    main()
