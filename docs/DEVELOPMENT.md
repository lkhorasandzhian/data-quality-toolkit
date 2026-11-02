# Development and testing

Use this guide if you want to modify the toolkit locally. Clone the repository and run these commands from the project root. Install Python 3.12 before starting.

The `toolkit/` directory contains the CLI in `src/`, automated tests in `tests/`, and sample data in `examples/`.

## Set up a virtual environment

Create `.venv` once, then activate it in each new terminal before installing dependencies, running the CLI, or running tests.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies after activation:

```bash
python -m pip install -r toolkit/requirements.txt
```

## Run the CLI locally

```bash
python toolkit/src/etl.py \
  --input toolkit/examples/events.csv \
  --output toolkit/examples/events.parquet \
  --required event_id,event_time,user_id \
  --unique event_id \
  --report toolkit/examples/quality.json
```

PowerShell:

```powershell
python toolkit/src/etl.py --input toolkit/examples/events.csv --output toolkit/examples/events.parquet --required event_id,event_time,user_id --unique event_id --report toolkit/examples/quality.json
```

## Run tests

With `.venv` activated:

```bash
python -m unittest discover -s toolkit/tests -v
```

## Build and test the Docker image

Docker must be installed and running.

```bash
docker build -t de-quality-toolkit .
docker run --rm -v "$PWD/toolkit/examples:/data" de-quality-toolkit \
  --input /data/events.csv \
  --output /data/events.parquet \
  --required event_id,event_time,user_id \
  --unique event_id \
  --report /data/quality.json
```

PowerShell:

```powershell
docker build -t de-quality-toolkit .
docker run --rm -v "${PWD}/toolkit/examples:/data" de-quality-toolkit --input /data/events.csv --output /data/events.parquet --required event_id,event_time,user_id --unique event_id --report /data/quality.json
```

[Back to README](../README.md)
