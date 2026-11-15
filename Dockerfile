# Multi-stage build for smaller final image
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
# Copy and install Python dependencies
COPY requirements.txt requirements-billing.txt ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
# Cloud (paid mode) deps: installed always so one image serves both modes; they
# are only imported when BILLING_ENABLED is set. Harmless/unused in self-host.
RUN pip install --no-cache-dir -r requirements-billing.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install FFmpeg, OpenCV deps, Node.js + npm + git (for yt-dlp JS + bgutil build).
# fontconfig + fonts-liberation back the subtitle font choices: without real
# fonts libass falls back to DejaVu for every UI option (issue #57).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    nodejs \
    npm \
    git \
    curl \
    fontconfig \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Deno JS runtime — required by yt-dlp for some extractor challenges.
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Helper token provider, baked in as a local Node script (no separate service).
RUN git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider /opt/bgutil-provider \
    && cd /opt/bgutil-provider/server \
    && npm install --no-audit --no-fund \
    && npx tsc \
    && npm cache clean --force
ENV BGUTIL_SCRIPT_PATH=/opt/bgutil-provider/server/build/generate_once.js

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# GPU runtime wiring — harmless no-ops on CPU builds / hosts without the
# NVIDIA runtime. LD_LIBRARY_PATH points at the pip-installed CUDA libs
# (paths simply don't exist in CPU images); DRIVER_CAPABILITIES asks the
# runtime for compute (CUDA) + video (NVENC) driver libs.
ENV LD_LIBRARY_PATH=/opt/venv/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/opt/venv/lib/python3.11/site-packages/nvidia/cu13/lib
ENV NVIDIA_DRIVER_CAPABILITIES=compute,video,utility

# NeMo-Speech.cpp runtime — transcription (parakeet-tdt-0.6b-v3 GGUF, CUDA).
# Prebuilt release archive with its user-space CUDA libs bundled, so the image
# needs no CUDA toolkit; the NVIDIA container runtime injects the driver.
# The archive is verified against the .sha256 published with the release.
ARG GPU=0
ARG NEMO_SPEECH_VERSION=0.3.0
RUN set -eux; \
    backend=cpu; \
    if [ "$GPU" = "1" ]; then backend=cuda; fi; \
    base="https://github.com/NVIDIA/NeMo-Speech.cpp/releases/download/v${NEMO_SPEECH_VERSION}"; \
    curl -fsSL -o /tmp/nemo.tar.gz "${base}/nemo-speech-${NEMO_SPEECH_VERSION}-linux-x86_64-${backend}.tar.gz"; \
    curl -fsSL -o /tmp/nemo.tar.gz.sha256 "${base}/nemo-speech-${NEMO_SPEECH_VERSION}-linux-x86_64-${backend}.tar.gz.sha256"; \
    echo "$(awk 'NR==1{print $1}' /tmp/nemo.tar.gz.sha256)  /tmp/nemo.tar.gz" | sha256sum -c -; \
    mkdir -p /opt/nemo-speech; \
    tar -xzf /tmp/nemo.tar.gz -C /opt/nemo-speech; \
    rm -f /tmp/nemo.tar.gz /tmp/nemo.tar.gz.sha256; \
    ln -sf "$(find /opt/nemo-speech -type f -name nemo-speech | head -1)" /usr/local/bin/nemo-speech
ENV NEMO_SPEECH_BIN=/usr/local/bin/nemo-speech

# Latest yt-dlp (nightly — it updates frequently) plus its helper plugin.
RUN pip install --upgrade --pre --no-cache-dir "yt-dlp[default]" bgutil-ytdlp-pot-provider

# Copy application code
COPY . .

# Register the bundled fonts (Anton for Impact) and the UI-name -> real-font
# aliases with fontconfig so libass resolves what the subtitle modal offers.
RUN mkdir -p /usr/local/share/fonts/openshorts \
    && cp fonts/*.ttf /usr/local/share/fonts/openshorts/ \
    && cp fonts/openshorts-fontmap.conf /etc/fonts/conf.d/60-openshorts.conf \
    && fc-cache -f

# Create a non-root user (Moved up)
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Create directories including Ultralytics cache config. /app/.cache/nemo-speech
# exists in-image (appuser-owned via the chown below) so a persistent volume
# mounted there inherits writable ownership for the ASR model downloads.
RUN mkdir -p /app/uploads /app/output /app/.cache/nemo-speech /tmp/Ultralytics
# Fix permissions: /app for code/uploads, /tmp/Ultralytics for AI cache
RUN chown -R appuser:appuser /app /tmp/Ultralytics

# Switch to non-root user
USER appuser

# Pre-download YOLO model on build (now running as appuser)
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI app. --proxy-headers + --forwarded-allow-ips trust the reverse
# proxy's X-Forwarded-Proto so generated URLs (e.g. the OAuth redirect_uri) use
# https in production instead of the internal http scheme.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
