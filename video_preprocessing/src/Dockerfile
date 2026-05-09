# Build from the src/ directory:
#   docker build -t videosearch .
#
# Run:
#   docker run -d --name videosearch \
#     -v /absolute/path/to/local-shared:/data \
#     videosearch
#
# Then exec in and run:
#   docker exec -it videosearch bash
#   python pipeline.py --shared /data --video osc
#   python agent/orchestrator.py osc

FROM python:3.11-slim

WORKDIR /app

# System packages (union of all stages)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libswscale-dev \
        libswresample-dev \
        libsndfile1 \
        libsndfile1-dev \
        libgl1 \
        curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install --prefer-binary \
        torch==2.11.0 torchaudio==2.11.0 \
        --index-url https://download.pytorch.org/whl/cpu && \
    pip install --prefer-binary -r /app/requirements.txt

COPY stage_ffmpeg0/        /app/stage_ffmpeg0/
COPY stage_librosa/        /app/stage_librosa/
COPY stage_ffmpeg1/        /app/stage_ffmpeg1/
COPY stage_ffmpeg2/        /app/stage_ffmpeg2/
COPY stage_deepspeech/     /app/stage_deepspeech/
ENV WHISPER_MODEL=/app/stage_deepspeech/whisper-base
ENV TRANSFORMERS_OFFLINE=1
ENV LLM_BASE_URL=http://10.0.5.22:1234/v1
ENV LLM_MODEL=gemma-4
COPY stage_ffmpeg3/        /app/stage_ffmpeg3/
COPY stage_object_detector/ /app/stage_object_detector/
COPY agent/                /app/agent/
COPY pipeline.py           /app/pipeline.py
VOLUME ["/data"]

CMD ["bash", "-c", "tail -f /dev/null"]
