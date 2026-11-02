import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]


class ETLTests(unittest.TestCase):
    def run_cli(self, csv: str):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        input_path = Path(temp.name) / "input.csv"
        output_path = Path(temp.name) / "output.parquet"
        report_path = Path(temp.name) / "quality.json"
        input_path.write_text(csv, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "src" / "etl.py"), "--input", str(input_path),
             "--output", str(output_path), "--required", "event_id,user_id",
             "--unique", "event_id", "--report", str(report_path)],
            capture_output=True, text=True,
        )
        return completed, output_path, json.loads(report_path.read_text(encoding="utf-8"))

    def test_valid_data_writes_parquet(self):
        result, output, report = self.run_cli("event_id,user_id\n1,20\n2,21\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(pl.read_parquet(output).height, 2)

    def test_duplicate_key_fails_without_writing_parquet(self):
        result, output, report = self.run_cli("event_id,user_id\n1,20\n1,21\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(output.exists())
        self.assertGreater(report["duplicate_key_rows"], 0)


if __name__ == "__main__":
    unittest.main()
