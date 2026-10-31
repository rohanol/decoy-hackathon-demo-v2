FROM python:3.11.17-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
COPY --chown=1000:1000 . /app/decoys/web/
RUN mkdir -p /logs /state && chown -R 1000:1000 /logs /state
USER 1000:1000
EXPOSE 8080
# One worker keeps JSONL writes serialized; no access log containing raw URLs.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "decoys.web.app:create_app()"]
