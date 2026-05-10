FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
COPY requirements.sys /tmp/systemreq.txt

# Install system packages (minimal for this service)
RUN apt-get update && \
    xargs -a /tmp/systemreq.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5011

CMD ["bash", "-c", "tail -f /dev/null"]
