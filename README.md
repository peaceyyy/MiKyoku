# AniMiKyoku: Anime Poster to OP/ED Retrieval Tool

AniMiKyoku is a lightweight tool that takes a single anime poster image as input and returns all associated opening and ending songs. It uses a combination of image embedding similarity and AniList metadata to quickly and accurately find anime theme music.

## Core Features

*   **Image-Based Identification:** Identify an anime from a poster image.
*   **Theme Song Retrieval:** Fetches all opening and ending themes for a given anime series, including all seasons.
*   **Local Vector Database:** Uses a local FAISS index for fast and offline similarity search.
*   **Metadata Integration:** Pulls detailed anime metadata from the AniList API.
*   **Automatic Database Expansion:** Can automatically add new, unrecognized posters to its local database.

## Tech Stack

*   **Frontend:** React, TypeScript, Vite
*   **Backend:** Python, FastAPI
*   **Machine Learning:** CLIP for image embeddings, FAISS for vector search.

## Getting Started

### Prerequisites

*   Conda (for backend Python environment)
*   Node.js and npm (for frontend)

### Installation and Running

1.  **Backend Setup:**
    *   Navigate to the `backend` directory.
    *   Create the conda environment: `conda env create -f environment.yml`
    *   Activate the environment: `conda activate animikyoku`
    *   Start the backend server: `python main.py`

2.  **Frontend Setup:**
    *   Navigate to the `frontend` directory.
    *   Install dependencies: `npm install`
    *   Start the frontend development server: `npm run dev`

3.  **Running the Application:**
    *   Alternatively, you can use the `start-program.ps1` script in the root directory to start both backend and frontend servers.

## Project Structure

The project is divided into two main components:

*   `/frontend`: Contains the React-based user interface for uploading images and viewing results.
*   `/backend`: Houses the FastAPI server, which handles image processing, embedding, similarity search, and communication with the AniList API.

The core logic for the retrieval-augmented generation (RAG) is located in `backend/rag/`. This includes the CLIP embedder, FAISS vector store, and ingestion pipeline.