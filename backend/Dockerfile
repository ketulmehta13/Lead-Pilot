FROM python:3.11-slim

# Slim by default: runtime packages only, CPU-only XGBoost, no PyTorch.
# RAG then uses EMBEDDINGS_BACKEND=hash (set in docker-compose.yml).
# For the real MiniLM embeddings build with WITH_EMBEDDINGS=1 (adds ~1 GB).
ARG WITH_EMBEDDINGS=0

# Long timeout + retries: slow links time out at pip's 15 s default.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

COPY requirements.txt requirements-embeddings.txt ./
# xgboost-cpu is the same `import xgboost` without the bundled CUDA libraries (~250 MB less).
# Cache mount: a failed or repeated build reuses already-downloaded wheels.
RUN --mount=type=cache,target=/root/.cache/pip \
    sed -i 's/^xgboost>=/xgboost-cpu>=/' requirements.txt \
    && pip install -r requirements.txt \
    && if [ "$WITH_EMBEDDINGS" = "1" ]; then \
         pip install -r requirements-embeddings.txt \
         && python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2')"; \
       fi

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]
