FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS uv

# Update system packages to get latest security fixes
RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*
# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/

# Install requirements using uv
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy the application code
COPY . /app/


# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the server with stdio communication
ENTRYPOINT ["uv", "--directory", "/app/src/wiz_mcp_server", "run", "--with", "mcp[cli]", "mcp", "run", "server.py"]
