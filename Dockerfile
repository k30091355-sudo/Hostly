# Hostly – Website (hostly-web)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOSTLY_DATA_DIR=/srv/hostly

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hostly ./hostly

# Nicht als root laufen (Benutzer 1000 = normaler Ubuntu-Benutzer in WSL)
RUN useradd --uid 1000 --create-home hostly
USER hostly

EXPOSE 8000
# --proxy-headers: echte Besucher-Adresse von Tailscale übernehmen (Port ist nur lokal offen)
CMD ["uvicorn", "hostly.web.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
