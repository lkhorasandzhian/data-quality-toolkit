# Usage

Run the toolkit in GitHub Actions or use the published Docker image. Neither option requires a local Python installation.

## GitHub Actions

Add this workflow to `.github/workflows/data-quality.yml` in the repository containing your CSV:

```yaml
name: Check data quality

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Validate CSV and write Parquet
        uses: lkhorasandzhian/data-quality-toolkit@main
        with:
          input: data/events.csv
          output: data/events.parquet
          required: event_id,event_time,user_id
          unique: event_id
```

Paths are relative to the checked-out repository. Failed validation fails the step; successful validation writes Parquet into the runner workspace. The JSON report appears in the step logs. This Docker action requires a Linux runner and builds its container from the toolkit's Dockerfile. For reproducible workflows, replace `@main` with a commit SHA.

## Docker image

Run the Docker image from the directory containing your `data` folder:

```bash
docker run --rm -v "$PWD/data:/data" ghcr.io/lkhorasandzhian/data-quality-toolkit:main \
  --input /data/events.csv \
  --output /data/events.parquet \
  --required event_id,event_time,user_id \
  --unique event_id \
  --report /data/quality.json
```

PowerShell:

```powershell
docker run --rm -v "${PWD}/data:/data" ghcr.io/lkhorasandzhian/data-quality-toolkit:main --input /data/events.csv --output /data/events.parquet --required event_id,event_time,user_id --unique event_id --report /data/quality.json
```

Docker downloads the image automatically if it is not available locally. The mounted folder receives `events.parquet` and `quality.json`. If the package is private, authenticate to GHCR first with a token that has package read permissions.

[Back to README](../README.md)
