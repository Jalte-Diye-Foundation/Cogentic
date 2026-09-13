"""Cogentic AI daily content pipeline entry point."""

import sys
from scheduler.daily_runner import run_daily_pipeline
from website_assets.update_assets import update_website_assets


def main() -> None:
    """Run the daily content pipeline: theme, generation, evaluation, poster."""
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_daily_pipeline(target_date=target_date)
    if result and not result.get("skipped"):
        update_website_assets(result)


if __name__ == "__main__":
    main()
