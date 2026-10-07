FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# First boot downloads the ~1.3 GB data bundle into the volume, hence the long healthcheck timeout.
CMD ["sh", "-c", "python scripts/fetch_data.py && alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
