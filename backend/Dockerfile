# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies for compiling C extensions (like scapy's dependencies or psutil fallbacks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml to install dependencies
COPY pyproject.toml .

# Install dependencies into user local directory
# This automatically parses pyproject.toml using setuptools
RUN pip install --user --no-cache-dir .

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install runtime system packages (libpcap for sniffing, iptables/lsof for adapters)
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
ENV PYTHONPATH=/app:$PYTHONPATH

# Copy application code
COPY backend/ ./backend/

# Expose default API & WebSocket port
EXPOSE 8600

# Set environment variables for production
ENV HOST=0.0.0.0
ENV PORT=8600

# Note: To run packet capture (Scapy sniffer) inside Docker, the container 
# must either be run as root, or with --cap-add=NET_ADMIN --cap-add=NET_RAW.
# By default, we run the socket_app ASGI target which includes FastAPI + Socket.IO.
CMD ["uvicorn", "backend.main:socket_app", "--host", "0.0.0.0", "--port", "8600"]
