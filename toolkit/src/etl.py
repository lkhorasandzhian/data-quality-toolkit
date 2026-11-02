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


def run() -> int:
    parser = argparse.ArgumentParser(description="CSV -> validated Parquet")
    parser.add_argument("--input", type=Path, required=True, help="Source CSV")
    parser.add_argument("--output", type=Path, required=True, help="Destination Parquet")
    parser.add_argument("--required", default="", help="Columns that must exist and contain no nulls (comma-separated)")
    parser.add_argument("--unique", default="", help="Unique key columns, optionally composite (comma-separated)")
    parser.add_argument("--report", type=Path, help="Optional JSON data-quality report")
    parser.add_argument("--min-rows", type=int, default=1, help="Minimum expected rows")
    args = parser.parse_args()

    if args.min_rows < 0:
        parser.error("--min-rows cannot be negative")
    if not args.input.is_file():
        parser.error(f"Input CSV not found: {args.input}")
    if args.input.resolve() == args.output.resolve():
        parser.error("Input and output paths must differ")

    required = column_list(args.required)
    key_columns = column_list(args.unique)
    nonnull = list(dict.fromkeys(required + key_columns))
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(args.input),
        "destination": str(args.output),
        "required_columns": required,
        "unique_key": key_columns,
        "status": "failed",
        "errors": [],
    }
    try:
        frame = pl.scan_csv(str(args.input), infer_schema_length=10000)
        available = frame.collect_schema().names()
        missing = [c for c in nonnull if c not in available]
        if missing:
            report["errors"].append(f"Missing columns: {', '.join(missing)}")
        else:
            aggregates = [pl.len().alias("_row_count")]
            aggregates += [pl.col(c).null_count().alias(f"_null_{i}") for i, c in enumerate(nonnull)]
            result = frame.select(aggregates).collect().row(0, named=True)
            count = int(result["_row_count"])
            nulls = {c: int(result[f"_null_{i}"]) for i, c in enumerate(nonnull)}
            report["rows"] = count
            report["null_counts"] = nulls
            if count < args.min_rows:
                report["errors"].append(f"Expected at least {args.min_rows} rows, got {count}")
            for c, number in nulls.items():
                if number:
                    report["errors"].append(f"Column '{c}' has {number} NULL values")
            if key_columns:
                duplicate_rows = int(frame.select(pl.struct(key_columns).is_duplicated().sum().alias("duplicates")).collect().item())
                report["duplicate_key_rows"] = duplicate_rows
                if duplicate_rows:
                    report["errors"].append(f"Found {duplicate_rows} rows with duplicated key values")
        if not report["errors"]:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            frame.sink_parquet(str(args.output), compression="zstd")
            report["status"] = "passed"
    except (OSError, ValueError, pl.exceptions.PolarsError) as exc:
        report["errors"].append(str(exc))

    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    print(encoded, file=sys.stdout if report["status"] == "passed" else sys.stderr)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(run())
