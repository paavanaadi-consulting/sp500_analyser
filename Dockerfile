FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sp500_analyser/ sp500_analyser/

ENV PYTHONUNBUFFERED=1

VOLUME ["/data"]
CMD ["python", "-m", "sp500_analyser", "--output-dir", "/data"]
