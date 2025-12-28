FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Prevent generation of .pyc files and enable stdout/stderr flush
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements and install system deps needed for some wheels
COPY requirements.txt ./

RUN apt-get update && apt-get install -y --no-install-recommends \
		build-essential \
		git \
		ca-certificates \
		libsndfile1 \
		libgl1 \
		libglib2.0-0 \
		libsm6 \
		libxext6 \
		libxrender1 \
	&& rm -rf /var/lib/apt/lists/*

# Upgrade pip and install PyTorch CPU wheels first (smaller than full CUDA)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio

# Install remaining Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ .

# Copy data (optional; persistent volumes on Fly can override)
COPY data/ ./data

# Expose port
EXPOSE 8000

# Run using simple uvicorn command; let Fly supply $PORT
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
