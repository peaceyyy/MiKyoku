# MiKyoku

AniMiKyoku is a web application designed to identify an anime series from a provided poster image and retrieve its opening, ending, and original soundtrack theme music. It uses a combination of fast, local vector search and a powerful generative AI model to provide a responsive and accurate user experience.

## Features

- **Image-Based Identification:** Users can upload an anime poster or screenshot to identify the series.
- **Hybrid Identification System:**
  - A fast initial search is performed using a local RAG (Retrieval-Augmented Generation) pipeline, which uses CLIP embeddings and a FAISS vector store for near-instant identification of known posters.
  - If the RAG pipeline is not confident in the result, the system falls back to the Google Gemini vision model for a more comprehensive analysis.
- **Theme Music Retrieval:** Once identified, the application fetches theme song data from the AnimeThemes API and supplements it with OSTs identified by Gemini.
- **Interactive Music Player:** Users can search for and listen to theme songs directly in the browser via an embedded YouTube player.
- **Community-Driven Database:** When a new anime is identified via Gemini, users can confirm the result to "ingest" the poster into the local RAG database, making future identifications faster for everyone.
- **Anime Discovery:** Includes features to browse currently trending anime from AniList.

## Technology Stack

### Frontend

- **Framework:** React
- **Build Tool:** Vite
- **Language:** TypeScript
- **Styling:** CSS (PostCSS)

### Backend

- **Framework:** FastAPI
- **Language:** Python
- **Environment:** Conda
- **Web Server:** Uvicorn

### AI

- **Generative AI:** Google Gemini Pro Vision
- **Vector Embeddings:** CLIP
- **Vector Store:** Facebook AI Similarity Search (FAISS)

### External Services

- **Anime Metadata:** [AniList API](httpss://anilist.gitbook.io/anilist-apiv2-docs/)
- **Theme Song Data:** [AnimeThemes.moe API](httpss://animethemes.docs.apiary.io/)
- **Music Source:** YouTube

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Git
- Node.js and npm
- Conda (or Miniconda/Anaconda)

### Installation

1. **Clone the repository:**

   ```sh
   git clone <your-repository-url>
   cd AniMiKyoku
   ```
2. **Configure Environment Variables:**

   - Navigate to the `backend` directory.
   - Copy the `.env.example` file to a new file named `.env`.
   - Open the `.env` file and add your Google Gemini API key:
     ```
     GEMINI_API_KEY="your_api_key_here"
     ```
3. **Frontend Setup:**

   ```sh
   cd frontend
   npm install
   ```
4. **Backend Setup:**

   - Ensure your Conda environment is active.
   - Create the Conda environment from the `environment.yml` file. This will install all necessary Python packages.

   ```sh
   conda env create -f environment.yml
   conda activate animikyoku
   ```

### Running the Application

#### For Windows Users

A PowerShell script is provided to automate the startup process.

1. Open PowerShell in the project root directory.
2. Run the script:

   ```powershell
   .\start-program.ps1
   ```

   This will install any missing dependencies and start both the frontend and backend servers in separate windows.

#### For macOS / Linux Users

You will need to run the frontend and backend in two separate terminal windows.

- **Terminal 1: Start the Backend**

  ```sh
  conda activate animikyoku
  cd backend
  python main.py
  ```

  The backend will be running at `http://localhost:8000`.
- **Terminal 2: Start the Frontend**

  ```sh
  cd frontend
  npm run dev
  ```

  The frontend will be accessible at `http://localhost:5173`.
