# CrackPulse website - Docker image (x86_64 aur ARM64 / AWS Graviton dono)
#
# Build (dono architecture ek saath, buildx chahiye):
#   docker buildx build --platform linux/amd64,linux/arm64 -t crackpulse .
# Local chalao:
#   docker run -p 8000:8000 -e AWS_BEARER_TOKEN_BEDROCK=... crackpulse
#
# Secrets kabhi image mein nahi: sirf runtime environment variables se aate hain
#   AWS_BEARER_TOKEN_BEDROCK   Bedrock API key (ya AWS par IAM role do, tab key ki zaroorat nahi)
#   BEDROCK_MODEL_ID           (optional) dusra model
# Baaki settings (optional): PORT=8000, MAX_UPLOAD_MB=100, KEEP_FILES_HOURS=24,
#   WEB_CONCURRENCY=2, GUNICORN_THREADS=4

# Python 3.12: numpy, opencv-python-headless, scikit-image, scipy - sabke ready wheels
# amd64 aur arm64 dono ke liye hain (kuch bhi source se compile nahi hota)
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# pehle sirf requirements -> code badalne par libraries dobara install nahi hoti (layer cache)
COPY requirements.txt .
RUN pip install --only-binary=:all: -r requirements.txt

COPY . .

# root ke bina chalao; sirf yeh folders likhne layak
RUN useradd --create-home --uid 10001 app \
    && mkdir -p uploads static/results measurements agent_logs \
    && chown -R app:app uploads static/results measurements agent_logs
USER app

EXPOSE 8000

# curl slim image mein nahi hai, isliye python se /health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
