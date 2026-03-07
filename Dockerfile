FROM python:3.12-slim
 
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y curl --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
 
COPY app/ .
 
# Utente non-root (best practice sicurezza)
RUN adduser --disabled-password --gecos '' appuser
USER appuser
 
EXPOSE 8080
CMD ["python", "main.py"]
