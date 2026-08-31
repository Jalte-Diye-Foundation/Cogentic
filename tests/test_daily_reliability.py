"""Focused tests for daily publishing reliability safeguards."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import report_workflow_status
from scheduler.daily_runner import run_daily_pipeline


class DailyReliabilityTests(unittest.TestCase):
    def test_reuses_archived_poster_and_marks_its_quote_used(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive = root / "website_assets" / "archive" / "2026-09-01"
            archive.mkdir(parents=True)
            (archive / "poster.jpg").write_bytes(b"poster")
            (archive / "metadata.json").write_text(
                json.dumps(
                    {
                        "theme": "Quality Education",
                        "quote": "Learning changes every horizon.",
                        "explanation": "Knowledge creates new possibilities.",
                    }
                ),
                encoding="utf-8",
            )
            config = {
                "paths": {
                    "output_dir": "output",
                    "website_assets_dir": "website_assets",
                    "used_quotes_log": "used_quotes_log.txt",
                    "log_file": "logs/cogentic.log",
                },
                "poster": {"output_filename": "poster.jpg"},
                "website": {"metadata_filename": "metadata.json"},
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            try:
                with patch("scheduler.daily_runner.ContentGenerator") as generator:
                    with patch("scheduler.daily_runner.date") as run_date:
                        run_date.today.return_value.isoformat.return_value = "2026-09-01"
                        result = run_daily_pipeline(str(config_path), str(root))
            finally:
                root_logger = logging.getLogger()
                for handler in root_logger.handlers[:]:
                    handler.close()
                    root_logger.removeHandler(handler)

            generator.assert_not_called()

            self.assertTrue(result["skipped"])
            self.assertEqual(result["content_source"], "existing_poster")
            self.assertEqual(
                (root / "output" / "2026-09-01" / "poster.jpg").read_bytes(),
                b"poster",
            )
            self.assertIn(
                "Learning changes every horizon.",
                (root / "used_quotes_log.txt").read_text(encoding="utf-8"),
            )

    def test_reports_csv_fallback_without_error_details(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            summary_path = os.path.join(temporary_directory, "summary.md")
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary_path}):
                report_workflow_status({"content_source": "csv_fallback_error"})

            summary = Path(summary_path).read_text(encoding="utf-8")
            self.assertIn("## Daily content fallback", summary)
            self.assertIn("review this workflow's logs", summary)
            self.assertNotIn("csv_fallback_error", summary)


if __name__ == "__main__":
    unittest.main()
