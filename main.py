"""Cogentic AI daily content pipeline entry point."""

from scheduler.daily_runner import run_daily_pipeline


def main() -> None:
    """Run the daily content pipeline: theme, generation, evaluation, poster."""
    run_daily_pipeline()


if __name__ == "__main__":
    main()
