# AniMiKyoku: Anime Poster to OP/ED Retrieval Tool

AniMiKyoku is a lightweight tool that takes a single anime poster image as input and returns all associated opening and ending songs. It uses a combination of image embedding similarity and AniList metadata to quickly and accurately find anime theme music.

## Core Features

* **Image-Based Identification:** Identify an anime from a poster image.
* **Theme Song Retrieval:** Fetches all opening and ending themes for a given anime series, including all seasons.
* **Local Vector Database:** Uses a local FAISS index for fast and offline similarity search.
* **Metadata Integration:** Pulls detailed anime metadata from the AniList API.
* **Automatic Database Expansion:** Can automatically add new, unrecognized posters to its local database.

## Tech Stack

* **Frontend:** React, TypeScript, Vite
* **Backend:** Python, FastAPI
* **Machine Learning:** CLIP for image embeddings, FAISS for vector search.

## Getting Started

### Prerequisites

* [uv](https://github.com/astral-sh/uv) (for backend Python project management)
* Node.js and npm (for frontend)

### Installation and Running

1. **Quick Start (Recommended):**
   * Run the unified startup script in PowerShell from the project root:
     ```powershell
     .\start-program.ps1
     ```
   * This verifies `uv`, synchronizes dependencies in `.venv`, starts the frontend in a new window, and launches the FastAPI backend.

2. **Manual Setup:**
   * **Backend:**
     * From the root directory, sync the environment:
       ```powershell
       uv sync
       ```
     * Start the backend server:
       ```powershell
       cd backend
       uv run python main.py
       ```
   * **Frontend:**
     * Navigate to the `frontend` directory:
       ```powershell
       cd frontend
       ```
     * Install dependencies:
       ```powershell
       npm install
       ```
     * Start the development server:
       ```powershell
       npm run dev
       ```

## Project Structure

The project is divided into two main components:

* `/frontend`: Contains the React-based user interface for uploading images and viewing results.
* `/backend`: Houses the FastAPI server, which handles image processing, embedding, similarity search, and communication with the AniList API.

The core logic for the retrieval-augmented generation (RAG) is located in `backend/rag/`. This includes the CLIP embedder, FAISS vector store, and ingestion pipeline.
