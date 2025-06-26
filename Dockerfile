FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create non-root user with home directory
RUN groupadd -r astrons && useradd -r -g astrons -d /home/astrons -m astrons
RUN chown -R astrons:astrons /app
RUN chown -R astrons:astrons /home/astrons
USER astrons

# Set up astropy cache directory
ENV XDG_CACHE_HOME=/home/astrons/.cache
RUN mkdir -p /home/astrons/.cache/astropy

# Default command to run the simulation
CMD ["python", "source/astroNS/astroNS.py", \
    "source/models/Simple/SimpleSensorCollectionModel.yml", \
    "--end_simtime=86400", \
    "--network_name", "simple_prototype", \
    "--node_stats", \
    "--node_stats_history", \
    "--epoch=2024-01-01T00:00:00.0z", \
    "-t"]
