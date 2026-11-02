FROM python:3.12-slim AS base
WORKDIR /app
COPY toolkit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY toolkit/src/etl.py .
ENTRYPOINT ["python", "/app/etl.py"]

FROM base AS test
COPY toolkit/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY toolkit/src/ toolkit/src/
COPY toolkit/tests/ toolkit/tests/
ENTRYPOINT ["python", "-m", "pytest"]
CMD ["toolkit/tests", "-v", "--color=yes", "-p", "no:cacheprovider"]

FROM base AS runtime
