FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# dlib-bin is useful on some local Windows setups, but Linux Docker builds need dlib.
RUN grep -v "^dlib-bin" requirements.txt > /tmp/requirements-docker.txt \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r /tmp/requirements-docker.txt \
    && python -m pip install dlib

COPY . .

EXPOSE 7860

CMD streamlit run app.py --server.port=${PORT:-7860} --server.address=0.0.0.0
