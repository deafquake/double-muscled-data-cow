# Use official Python image
FROM pytorch/pytorch:2.10.0-cuda13.0-cudnn9-runtime
ENTRYPOINT []
# Set working directory
WORKDIR /app
COPY requirements.txt .
# Install system dependencies for your packages
COPY requirements.sys /tmp/systemreq.txt

# Install system packages
RUN pip install --upgrade pip --break-system-packages && \
    pip install --break-system-packages -r requirements.txt

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev

COPY . .

# Expose the port your Flask app runs on
EXPOSE 5004

# Run the application
CMD ["bash", "-c", "tail -f /dev/null"]