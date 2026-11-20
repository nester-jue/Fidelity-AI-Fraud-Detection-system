FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies (psycopg2 needs build-essential and libpq-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement file and install Python deps
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source code
COPY backend/ ./backend/

# Expose the FastAPI port
EXPOSE 8010

# Command to run the API
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8010"]
