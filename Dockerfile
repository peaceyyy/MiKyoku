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

# Copy the init-data script
COPY backend/init-data.sh /usr/local/bin/init-data.sh
RUN chmod +x /usr/local/bin/init-data.sh

# Copy initial data to a non-mounted location
COPY data/ ./data_initial

# Expose port
EXPOSE 8000

# Run the initialization script then start the app
CMD ["init-data.sh"]
