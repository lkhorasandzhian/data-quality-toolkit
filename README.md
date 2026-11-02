# Data Quality Toolkit

A minimal data engineering CLI for **CSV → Parquet** with contract checks and a machine-readable JSON quality report.

Checks:
- required columns exist
- required and unique-key columns have no NULL values
- a single or composite key has no duplicates
- dataset meets a minimum row count (default: 1)

If checks fail, exit code is `1`, an error report is emitted, and output Parquet is not written.

> [!IMPORTANT]
> Validation results depend on how you configure the basic data quality checks currently provided by the toolkit.

## How to Use

The toolkit is designed for use with **GitHub Actions** or as a **Docker image**. To get started, follow one of these guides:

- [GitHub Actions setup instructions](docs/USAGE.md#github-actions)
- [Docker image usage instructions](docs/USAGE.md#docker-image)

## Development

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for virtual environment setup, local CLI usage, tests, and Docker builds.

> [!NOTE]
> This setup is optional and only needed if you want to modify the project locally.
