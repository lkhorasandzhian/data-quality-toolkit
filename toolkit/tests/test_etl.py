import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]


class ETLTests(unittest.TestCase):
    def run_cli(
        self,
        csv: str,
        *,
        required: str = "event_id,user_id",
        unique: str = "event_id",
        min_rows: int = 1,
    ):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        input_path = Path(temp.name) / "input.csv"
        output_path = Path(temp.name) / "output.parquet"
        report_path = Path(temp.name) / "quality.json"
        input_path.write_text(csv, encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable, str(ROOT / "src" / "etl.py"),
                "--input", str(input_path),
                "--output", str(output_path),
                "--required", required,
                "--unique", unique,
                "--min-rows", str(min_rows),
                "--report", str(report_path),
            ],
            capture_output=True, text=True,
        )
        self.assertTrue(report_path.is_file(), completed.stderr)
        return completed, output_path, json.loads(report_path.read_text(encoding="utf-8"))

    def test_valid_data_writes_parquet(self):
        result, output, report = self.run_cli("event_id,user_id\n1,20\n2,21\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["null_counts"], {"event_id": 0, "user_id": 0})
        self.assertEqual(report["duplicate_key_rows"], 0)
        self.assertEqual(pl.read_parquet(output).to_dict(as_series=False), {
            "event_id": [1, 2], "user_id": [20, 21],
        })
        self.assertEqual(json.loads(result.stdout), report)
        self.assertEqual(result.stderr, "")

    def test_duplicate_key_fails_without_writing_parquet(self):
        result, output, report = self.run_cli("event_id,user_id\n1,20\n1,21\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(output.exists())
        self.assertEqual(report["duplicate_key_rows"], 2)
        self.assertEqual(json.loads(result.stderr), report)
        self.assertEqual(result.stdout, "")

    def test_missing_required_or_key_column_fails(self):
        for required, unique, missing in [
            ("event_id,user_id", "event_id", "user_id"),
            ("event_id", "user_id", "user_id"),
        ]:
            with self.subTest(required=required, unique=unique):
                result, output, report = self.run_cli(
                    "event_id\n1\n2\n", required=required, unique=unique,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["errors"], [f"Missing columns: {missing}"])
                self.assertFalse(output.exists())

    def test_null_required_column_fails(self):
        result, output, report = self.run_cli("event_id,user_id\n1,20\n2,\n")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["null_counts"]["user_id"], 1)
        self.assertIn("Column 'user_id' has 1 NULL values", report["errors"])
        self.assertFalse(output.exists())

    def test_null_key_column_fails_even_when_not_required(self):
        result, output, report = self.run_cli(
            "event_id,user_id\n1,20\n,21\n", required="user_id",
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["null_counts"]["event_id"], 1)
        self.assertIn("Column 'event_id' has 1 NULL values", report["errors"])
        self.assertFalse(output.exists())

    def test_composite_key_allows_repeated_individual_values(self):
        result, output, report = self.run_cli(
            "event_id,user_id\n1,20\n1,21\n2,20\n",
            unique="event_id,user_id",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["duplicate_key_rows"], 0)
        self.assertEqual(report["unique_key"], ["event_id", "user_id"])
        self.assertEqual(pl.read_parquet(output).height, 3)

    def test_duplicate_composite_key_fails(self):
        result, output, report = self.run_cli(
            "event_id,user_id\n1,20\n1,21\n1,20\n",
            unique="event_id,user_id",
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["duplicate_key_rows"], 2)
        self.assertIn("Found 2 rows with duplicated key values", report["errors"])
        self.assertFalse(output.exists())

    def test_minimum_row_count_boundary(self):
        for csv, min_rows, row_count, should_pass in [
            ("event_id,user_id\n", 1, 0, False),
            ("event_id,user_id\n", 0, 0, True),
            ("event_id,user_id\n1,20\n", 2, 1, False),
            ("event_id,user_id\n1,20\n2,21\n", 2, 2, True),
        ]:
            with self.subTest(min_rows=min_rows, row_count=row_count):
                result, output, report = self.run_cli(csv, min_rows=min_rows)
                self.assertEqual(result.returncode, 0 if should_pass else 1, result.stderr)
                self.assertEqual(report["status"], "passed" if should_pass else "failed")
                self.assertEqual(report["rows"], row_count)
                self.assertEqual(output.exists(), should_pass)
                if should_pass:
                    self.assertEqual(report["errors"], [])
                    self.assertEqual(pl.read_parquet(output).height, row_count)
                else:
                    self.assertIn(
                        f"Expected at least {min_rows} rows, got {row_count}",
                        report["errors"],
                    )


if __name__ == "__main__":
    unittest.main()
