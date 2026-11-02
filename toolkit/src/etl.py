"""Validate a CSV data contract and convert a valid dataset to Parquet."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


def column_list(value: str) -> list[str]:
    """Parse a comma-separated list without repeated or empty names."""
    return list(dict.fromkeys(name.strip() for name in value.split(",") if name.strip()))


def parse_args() -> argparse.Namespace:
    """Parse CLI options and reject invalid arguments before reading data."""
    parser = argparse.ArgumentParser(description="CSV -> validated Parquet")
    parser.add_argument("--input", type=Path, required=True, help="Source CSV")
    parser.add_argument("--output", type=Path, required=True, help="Destination Parquet")
    parser.add_argument(
        "--required", default="",
        help="Columns that must exist and contain no nulls (comma-separated)",
    )
    parser.add_argument(
        "--unique", default="",
        help="Unique key columns, optionally composite (comma-separated)",
    )
    parser.add_argument("--report", type=Path, help="Optional JSON data-quality report")
    parser.add_argument("--min-rows", type=int, default=1, help="Minimum expected rows")
    args = parser.parse_args()

    if args.min_rows < 0:
        parser.error("--min-rows cannot be negative")
    if not args.input.is_file():
        parser.error(f"Input CSV not found: {args.input}")
    if args.input.resolve() == args.output.resolve():
        parser.error("Input and output paths must differ")

    return args


def validate_data(
    frame: pl.LazyFrame,
    required_columns: list[str],
    key_columns: list[str],
    min_rows: int,
    report: dict,
) -> None:
    """Add contract errors and dataset metrics to the report as checks complete."""
    errors = report["errors"]

    # Key columns must also exist and contain no nulls, even if not required explicitly.
    non_null_columns = list(dict.fromkeys(required_columns + key_columns))
    available_columns = frame.collect_schema().names()
    missing_columns = [
        column for column in non_null_columns if column not in available_columns
    ]
    if missing_columns:
        errors.append(f"Missing columns: {', '.join(missing_columns)}")
        return

    aggregates = [pl.len().alias("_row_count")]
    aggregates.extend(
        pl.col(column).null_count().alias(f"_null_{index}")
        for index, column in enumerate(non_null_columns)
    )
    statistics = frame.select(aggregates).collect().row(0, named=True)
    row_count = int(statistics["_row_count"])
    null_counts = {
        column: int(statistics[f"_null_{index}"])
        for index, column in enumerate(non_null_columns)
    }
    report["rows"] = row_count
    report["null_counts"] = null_counts

    if row_count < min_rows:
        errors.append(f"Expected at least {min_rows} rows, got {row_count}")
    for column, null_count in null_counts.items():
        if null_count:
            errors.append(f"Column '{column}' has {null_count} NULL values")

    if key_columns:
        # Count every row in a duplicate group, including its first occurrence.
        duplicate_count_query = frame.select(
            pl.struct(key_columns).is_duplicated().sum().alias("duplicates")
        )
        duplicate_rows = int(duplicate_count_query.collect().item())
        report["duplicate_key_rows"] = duplicate_rows
        if duplicate_rows:
            errors.append(f"Found {duplicate_rows} rows with duplicated key values")


def write_report(report: dict, report_path: Path | None) -> None:
    """Save the optional JSON report and print it to the appropriate stream."""
    report_json = json.dumps(report, ensure_ascii=False, indent=2)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_json + "\n", encoding="utf-8")
    report_stream = sys.stdout if report["status"] == "passed" else sys.stderr
    print(report_json, file=report_stream)


def run() -> int:
    args = parse_args()
    required_columns = column_list(args.required)
    key_columns = column_list(args.unique)
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(args.input),
        "destination": str(args.output),
        "required_columns": required_columns,
        "unique_key": key_columns,
        "status": "failed",
        "errors": [],
    }
    try:
        frame = pl.scan_csv(str(args.input), infer_schema_length=10000)
        validate_data(frame, required_columns, key_columns, args.min_rows, report)
        if not report["errors"]:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            frame.sink_parquet(str(args.output), compression="zstd")
            report["status"] = "passed"
    except (OSError, ValueError, pl.exceptions.PolarsError) as exc:
        report["errors"].append(str(exc))

    write_report(report, args.report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(run())
