FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

ENV ENVIRONMENT=production

EXPOSE 8080

CMD ["python", "main.py"]
