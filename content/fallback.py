"""CSV fallback content and duplicate quote tracking with date-aware event validation."""

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
    """Provides unused quotes from theme-specific CSV files with date and event validation."""

    def __init__(self, config: dict[str, Any], project_root: str) -> None:
        self._config = config
        self._project_root = project_root
        self._used_quotes_log = self._resolve_path(config["paths"]["used_quotes_log"])
        self._emergency = config.get(
            "emergency_failsafe",
            {
                "quote": "The best time to plant a tree was twenty years ago. The second best time is now.",
                "explanation": "Every small step we take today shapes the world we live in tomorrow.",
            },
        )

    def _resolve_path(self, relative_path: str) -> str:
        return os.path.join(self._project_root, relative_path)

    def get_fallback_quote(
        self,
        theme: str,
        today_event: dict[str, Any] | None = None,
        current_date_str: str | None = None,
    ) -> dict[str, str]:
        """
        Pull an unused quote from the CSV mapped to the given theme.
        Guarantees that event-based quotes are only selected when relevant to today_event or current_date.
        """
        logger.warning("Triggering CSV fallback for theme: %s", theme)
        theme_config = self._config["themes"].get(theme)
        if not theme_config:
            logger.error("No theme configuration found for: %s", theme)
            return self._emergency_failsafe()

        csv_file = self._resolve_path(theme_config.get("csv_fallback", ""))
        if not os.path.exists(csv_file):
            logger.error("Missing CSV fallback file for %s: %s", theme, csv_file)
            return self._emergency_failsafe()

        used_quotes = load_used_quotes(self._used_quotes_log)
        target_event_name = today_event.get("event") if today_event else None

        fallback_content = self._read_unused_csv_quote(
            csv_file=csv_file,
            used_quotes=used_quotes,
            target_event=target_event_name,
            target_date=current_date_str,
            is_event_theme=(theme == "Foundation Events" or bool(today_event)),
        )

        if fallback_content:
            mark_quote_used(fallback_content["quote"], self._used_quotes_log)
            logger.info("Retrieved fallback quote from CSV: %s", csv_file)
            return fallback_content

        logger.warning("No matching unused quote found in %s; using failsafe.", csv_file)
        return self._emergency_failsafe()

    def _read_unused_csv_quote(
        self,
        csv_file: str,
        used_quotes: set[str],
        target_event: str | None = None,
        target_date: str | None = None,
        is_event_theme: bool = False,
    ) -> dict[str, str] | None:
        """
        Read an unused quote from a CSV file.
        Supports both headered and headerless CSVs.
        If is_event_theme is True, strictly matches target_event or target_date.
        """
        try:
            with open(csv_file, "r", encoding="utf-8-sig") as handle:
                reader = list(csv.reader(handle))
        except Exception as exc:
            logger.error("Failed to read CSV file %s: %s", csv_file, exc)
            return None

        if not reader:
            return None

        # Filter out completely empty rows
        rows = [r for r in reader if r and any(cell.strip() for cell in r)]
        if not rows:
            return None

        # Check if first row is a header row
        first_row_lower = [c.strip().lower() for c in rows[0]]
        known_headers = {"quote", "caption", "occasion", "event", "heading", "date", "month"}
        has_headers = any(h in known_headers for h in first_row_lower)

        if has_headers:
            headers = first_row_lower
            data_rows = rows[1:]
            quote_idx = headers.index("quote") if "quote" in headers else -1
            caption_idx = headers.index("caption") if "caption" in headers else -1
            occasion_idx = headers.index("occasion") if "occasion" in headers else -1
            event_idx = headers.index("event") if "event" in headers else -1
            date_idx = headers.index("date") if "date" in headers else -1
        else:
            # Headerless CSV (e.g. quotes.csv where col0=quote, col1=caption)
            data_rows = rows
            quote_idx = 0
            caption_idx = 1 if len(rows[0]) > 1 else -1
            occasion_idx = -1
            event_idx = -1
            date_idx = -1

        for row in data_rows:
            if quote_idx == -1 or len(row) <= quote_idx:
                continue

            row_quote = row[quote_idx].strip()
            if not row_quote or row_quote in used_quotes:
                continue

            # Extract explanation / caption / occasion
            row_explanation = ""
            if caption_idx != -1 and len(row) > caption_idx and row[caption_idx].strip():
                row_explanation = row[caption_idx].strip()
            elif occasion_idx != -1 and len(row) > occasion_idx and row[occasion_idx].strip():
                row_explanation = f"Observing {row[occasion_idx].strip()}."
            elif event_idx != -1 and len(row) > event_idx and row[event_idx].strip():
                row_explanation = f"Observing {row[event_idx].strip()}."

            # Date/Event filtering for time-bound events
            if is_event_theme:
                # If target event or date is specified, verify this row matches
                row_event_name = ""
                if occasion_idx != -1 and len(row) > occasion_idx:
                    row_event_name = row[occasion_idx].strip().lower()
                elif event_idx != -1 and len(row) > event_idx:
                    row_event_name = row[event_idx].strip().lower()

                row_date = ""
                if date_idx != -1 and len(row) > date_idx:
                    row_date = row[date_idx].strip()

                if target_event:
                    t_event = target_event.strip().lower()
                    if t_event not in row_event_name and row_event_name not in t_event:
                        # Event name did not match; skip row
                        continue
                elif target_date:
                    # If target date is given (e.g., '08-15' or '2026-08-15'), check match
                    if target_date not in row_date:
                        continue
                else:
                    # No target event and no target date -> do NOT serve random dated event rows!
                    continue

            return {
                "quote": row_quote.replace('"', ""),
                "explanation": row_explanation.replace('"', ""),
            }

        return None

    def _emergency_failsafe(self) -> dict[str, str]:
        logger.warning("Using emergency hardcoded failsafe quote.")
        return {
            "quote": self._emergency["quote"],
            "explanation": self._emergency["explanation"],
        }
