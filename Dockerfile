# Use an official Miniconda image as a parent image
FROM continuumio/miniconda3:latest

# Set the working directory in the container
WORKDIR /app

# Copy the environment file to the working directory
COPY environment.yml .

# Create the conda environment from the environment.yml file
# This will install all necessary packages including pytorch, faiss-cpu, etc.
RUN conda env create -f environment.yml

# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "animikyoku", "/bin/bash", "-c"]

# Copy the rest of the backend application code
COPY backend/ .

# Copy the initial data directory into the image
# This will be overwritten by the persistent disk on Fly.io, but is good for base state
COPY data/ ./data

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application
# The port will be set by Fly.io's PORT environment variable
CMD ["sh", "-lc", "conda run -n animikyoku uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
