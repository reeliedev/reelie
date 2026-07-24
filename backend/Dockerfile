# Reelie API — production image (the FastAPI service).
# Note: self-serve generation shells out to the video pipeline, which is NOT in
# this image; in production that runs as a separate worker (see README). The API
# deploys and runs fine on its own; generation jobs error cleanly if the pipeline
# isn't reachable.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REELIE_ENV=prod

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

EXPOSE 8000
# Run migrations, then serve. $PORT is provided by most hosts; default 8000.
# FORWARDED_ALLOW_IPS lets uvicorn trust the host's proxy X-Forwarded-For so the
# real client IP reaches rate limiting (Render terminates TLS at its proxy).
CMD ["sh", "-c", "alembic upgrade head && FORWARDED_ALLOW_IPS='*' gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 120"]
