FROM python:3.11-slim

# Install system dependencies including git for version control
RUN apt-get update && apt-get install -y --no-install-recommends \
gcc \
curl \
git \
&& rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy shared module first (dependency)
COPY shared/pyproject.toml ./shared/
COPY shared/src ./shared/src

# Copy market-scraper
COPY market-scraper/pyproject.toml ./market-scraper/
COPY market-scraper/README.md ./market-scraper/
COPY market-scraper/src ./market-scraper/src
COPY market-scraper/config ./market-scraper/config

# Install shared module
RUN cd /app/shared && uv pip install --system .

# Install market-scraper
RUN cd /app/market-scraper && uv pip install --system .

# Create directories
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 3845

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
 CMD curl -f http://localhost:3845/health/live || exit 1

# Run the server from market-scraper directory
WORKDIR /app/market-scraper
CMD ["python", "-m", "market_scraper", "server", "--host", "0.0.0.0", "--port", "3845"]
