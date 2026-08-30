"""CSV fallback content and duplicate quote tracking."""

from __future__ import annotations

import csv
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def load_used_quotes(log_path: str) -> set[str]:
    """Load previously used quotes from the persistent log file."""
    if not os.path.exists(log_path):
        return set()
    with open(log_path, "r", encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def is_quote_used(quote: str, log_path: str) -> bool:
    """Return True if the quote has already been used."""
    normalized = quote.strip()
    if not normalized:
        return False
    return normalized in load_used_quotes(log_path)


def mark_quote_used(quote: str, log_path: str) -> None:
    """Append a quote to the used-quotes log to prevent future reuse."""
    normalized = quote.strip()
    if not normalized:
        return
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(normalized + "\n")
    logger.info("Marked quote as used: %s", normalized[:80])


class FallbackProvider:
    """Provides unused quotes from theme-specific CSV files."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        self._used_quotes_log = self._resolve_path(config["paths"]["used_quotes_log"])
        self._emergency = config["emergency_failsafe"]

    def _resolve_path(self, relative_path: str) -> str:
        return os.path.join(self._project_root, relative_path)

    def get_fallback_quote(self, theme: str, event: dict | None = None) -> dict[str, str]:
        """Pull an unused quote from the CSV mapped to the given theme."""
        logger.warning("Triggering CSV fallback for theme: %s", theme)
        theme_config = self._config["themes"].get(theme)
        if not theme_config:
            logger.error("No theme configuration found for: %s", theme)
            return self._emergency_failsafe()

        csv_file = self._resolve_path(theme_config["csv_fallback"])
        if not os.path.exists(csv_file):
            logger.error("Missing CSV fallback file for %s: %s", theme, csv_file)
            return self._emergency_failsafe()

        used_quotes = load_used_quotes(self._used_quotes_log)
        event_name = event["event"] if event else None
        fallback_content = self._read_unused_csv_quote(csv_file, used_quotes, event_name)
        if fallback_content:
            mark_quote_used(fallback_content["quote"], self._used_quotes_log)
            logger.info("Retrieved fallback quote from CSV: %s", csv_file)
            return fallback_content

        logger.critical("No unused quotes remain in CSV: %s", csv_file)
        return self._emergency_failsafe()

    def _read_unused_csv_quote(
        self, csv_file: str, used_quotes: set[str], event_name: str | None = None
    ) -> dict[str, str] | None:
        with open(csv_file, "r", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            headers: list[str] = []
            for row in reader:
                if row and any(cell.strip() for cell in row):
                    headers = [cell.strip().lower() for cell in row]
                    break

            quote_idx = headers.index("quote") if "quote" in headers else -1
            caption_idx = headers.index("caption") if "caption" in headers else -1
            occasion_idx = headers.index("occasion") if "occasion" in headers else -1

            all_rows = list(reader)

        # When today has a specific event, only use rows whose occasion matches it
        if event_name and occasion_idx != -1:
            candidate_rows = [
                r for r in all_rows
                if len(r) > occasion_idx and r[occasion_idx].strip().lower() == event_name.lower()
            ]
            # Fall back to any row if no occasion-matched rows exist
            if not candidate_rows:
                logger.warning("No CSV rows for event '%s'; using generic fallback row.", event_name)
                candidate_rows = all_rows
        else:
            candidate_rows = all_rows

        for row in candidate_rows:
            if not row or quote_idx == -1 or len(row) <= quote_idx:
                continue

            row_quote = row[quote_idx].strip()
            row_explanation = ""
            if caption_idx != -1 and len(row) > caption_idx:
                row_explanation = row[caption_idx].strip()
            elif occasion_idx != -1 and len(row) > occasion_idx:
                # Only use the occasion label if it matches today's event
                occasion_val = row[occasion_idx].strip()
                if event_name and occasion_val.lower() == event_name.lower():
                    row_explanation = f"Observing {occasion_val}."

            if row_quote and row_quote not in used_quotes:
                return {
                    "quote": row_quote.replace('"', ""),
                    "explanation": row_explanation.replace('"', ""),
                    "long_explanation": "",
                }
        return None

    def _emergency_failsafe(self) -> dict[str, str]:
        logger.warning("Using emergency hardcoded failsafe quote.")
        return {
            "quote": self._emergency["quote"],
            "explanation": self._emergency["explanation"],
            "long_explanation": "",
        }
