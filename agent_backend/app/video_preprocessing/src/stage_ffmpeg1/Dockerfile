# Use official Python image
FROM python:3.14-slim

# Set working directory
WORKDIR /app
COPY requirements.txt .
# Install system dependencies for your packages
COPY requirements.sys /tmp/systemreq.txt

# Install system packages
RUN apt-get update && \
    xargs -a /tmp/systemreq.txt apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt 

COPY . .

# Expose the port your Flask app runs on
EXPOSE 5006

# Run the application
CMD ["bash", "-c", "tail -f /dev/null"]