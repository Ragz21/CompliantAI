# ───────────────────────── 1) builder ─────────────────────────
FROM --platform=$BUILDPLATFORM python:3.11-slim AS builder

ARG TARGETPLATFORM
WORKDIR /opt/wheels

# System dependencies for building Python wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential libopenblas-dev libgl1 libsndfile1 curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel -r requirements.txt -w /opt/wheels


# ───────────────────────── 2) runtime ─────────────────────────
FROM --platform=$TARGETPLATFORM python:3.11-slim

WORKDIR /opt/app

# Install system dependencies needed at runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git texlive-full libopenblas-dev libgl1 libsndfile1 curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY --from=builder /opt/wheels /wheels
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels numpy==1.26.4 --no-deps && \
    pip install --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# Copy source code
COPY . .

# Setup entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create required directories
RUN mkdir -p input_data output_data models core/db/vector_db mlruns

# Install Gunicorn
RUN pip install gunicorn gevent

EXPOSE 5001

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "-k", "gthread", "-w", "4", "-b", "0.0.0.0:5001", "website.index:app"]
