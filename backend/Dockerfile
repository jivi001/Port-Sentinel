# Stage 1: Build dependencies
FROM python:3.9-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.9-slim

WORKDIR /app

# Install runtime system dependencies (e.g. for scapy and pfctl/iptables)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpcap0.8 \
    iptables \
    net-tools \
    iproute2 \
    lsof \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY backend/ ./backend/
COPY .env .env

# Expose the API port
EXPOSE 8600

# We use uvicorn to run the app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8600"]
