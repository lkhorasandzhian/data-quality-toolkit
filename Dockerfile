FROM python:3.12-slim
WORKDIR /app
COPY toolkit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY toolkit/src/etl.py .
ENTRYPOINT ["python", "/app/etl.py"]
