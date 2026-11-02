import json
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def run_cli(tmp_path):
    def invoke(
        csv: str,
        *,
        required: str = "event_id,user_id",
        unique: str = "event_id",
        min_rows: int = 1,
    ):
        input_path = tmp_path / "input.csv"
        output_path = tmp_path / "output.parquet"
        report_path = tmp_path / "quality.json"
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
        assert report_path.is_file(), completed.stderr
        return completed, output_path, json.loads(report_path.read_text(encoding="utf-8"))

    return invoke


def test_valid_data_writes_parquet(run_cli):
    result, output, report = run_cli("event_id,user_id\n1,20\n2,21\n")
    assert result.returncode == 0, result.stderr
    assert report["status"] == "passed"
    assert report["errors"] == []
    assert report["rows"] == 2
    assert report["null_counts"] == {"event_id": 0, "user_id": 0}
    assert report["duplicate_key_rows"] == 0
    assert pl.read_parquet(output).to_dict(as_series=False) == {
        "event_id": [1, 2], "user_id": [20, 21],
    }
    assert json.loads(result.stdout) == report
    assert result.stderr == ""


def test_duplicate_key_fails_without_writing_parquet(run_cli):
    result, output, report = run_cli("event_id,user_id\n1,20\n1,21\n")
    assert result.returncode == 1
    assert report["status"] == "failed"
    assert not output.exists()
    assert report["duplicate_key_rows"] == 2
    assert json.loads(result.stderr) == report
    assert result.stdout == ""


@pytest.mark.parametrize(
    "required,unique,missing",
    [
        ("event_id,user_id", "event_id", "user_id"),
        ("event_id", "user_id", "user_id"),
    ],
    ids=["required-column", "key-column"],
)
def test_missing_required_or_key_column_fails(run_cli, required, unique, missing):
    result, output, report = run_cli(
        "event_id\n1\n2\n", required=required, unique=unique,
    )
    assert result.returncode == 1, result.stderr
    assert report["status"] == "failed"
    assert report["errors"] == [f"Missing columns: {missing}"]
    assert not output.exists()


def test_null_required_column_fails(run_cli):
    result, output, report = run_cli("event_id,user_id\n1,20\n2,\n")
    assert result.returncode == 1, result.stderr
    assert report["status"] == "failed"
    assert report["null_counts"]["user_id"] == 1
    assert "Column 'user_id' has 1 NULL values" in report["errors"]
    assert not output.exists()


def test_null_key_column_fails_even_when_not_required(run_cli):
    result, output, report = run_cli(
        "event_id,user_id\n1,20\n,21\n", required="user_id",
    )
    assert result.returncode == 1, result.stderr
    assert report["status"] == "failed"
    assert report["null_counts"]["event_id"] == 1
    assert "Column 'event_id' has 1 NULL values" in report["errors"]
    assert not output.exists()


def test_composite_key_allows_repeated_individual_values(run_cli):
    result, output, report = run_cli(
        "event_id,user_id\n1,20\n1,21\n2,20\n",
        unique="event_id,user_id",
    )
    assert result.returncode == 0, result.stderr
    assert report["status"] == "passed"
    assert report["duplicate_key_rows"] == 0
    assert report["unique_key"] == ["event_id", "user_id"]
    assert pl.read_parquet(output).height == 3


def test_duplicate_composite_key_fails(run_cli):
    result, output, report = run_cli(
        "event_id,user_id\n1,20\n1,21\n1,20\n",
        unique="event_id,user_id",
    )
    assert result.returncode == 1, result.stderr
    assert report["status"] == "failed"
    assert report["duplicate_key_rows"] == 2
    assert "Found 2 rows with duplicated key values" in report["errors"]
    assert not output.exists()


@pytest.mark.parametrize(
    "csv,min_rows,row_count,should_pass",
    [
        ("event_id,user_id\n", 1, 0, False),
        ("event_id,user_id\n", 0, 0, True),
        ("event_id,user_id\n1,20\n", 2, 1, False),
        ("event_id,user_id\n1,20\n2,21\n", 2, 2, True),
    ],
    ids=["empty-rejected", "empty-allowed", "below-minimum", "at-minimum"],
)
def test_minimum_row_count_boundary(run_cli, csv, min_rows, row_count, should_pass):
    result, output, report = run_cli(csv, min_rows=min_rows)
    assert result.returncode == (0 if should_pass else 1), result.stderr
    assert report["status"] == ("passed" if should_pass else "failed")
    assert report["rows"] == row_count
    assert output.exists() == should_pass
    if should_pass:
        assert report["errors"] == []
        assert pl.read_parquet(output).height == row_count
    else:
        assert f"Expected at least {min_rows} rows, got {row_count}" in report["errors"]
