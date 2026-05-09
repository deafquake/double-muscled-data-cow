# Use official Python image
FROM pytorch/pytorch:2.10.0-cuda13.0-cudnn9-runtime
ENTRYPOINT []
# Set working directory
WORKDIR /app
COPY requirements.txt .
# Install system dependencies for your packages
COPY requirements.sys /tmp/systemreq.txt

# Install system packages and build tools first so pip can use binary wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    libatlas-base-dev \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev && \
    rm -rf /var/lib/apt/lists/*

# Upgrade packaging tools and prefer binary wheels to avoid building numpy from source
RUN pip install --upgrade pip setuptools wheel --break-system-packages && \
    pip install --break-system-packages --prefer-binary -r requirements.txt

COPY . .

# Expose the port your Flask app runs on
EXPOSE 5010

# Run the application
CMD ["bash", "-c", "tail -f /dev/null"]