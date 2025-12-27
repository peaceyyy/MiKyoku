# AniMiKyoku Deployment Guide

This guide provides step-by-step instructions for deploying the AniMiKyoku application online. The recommended setup uses:

- **Backend (Python/FastAPI):** Deployed on **Render** as a Dockerized web service.
- **Frontend (React/Vite):** Deployed on **Vercel** as a static site.

This hybrid approach leverages the strengths of each platform: Render's robust Docker and persistent disk support for the complex backend, and Vercel's world-class network for a fast frontend experience.

---

### ⚠️ Important Prerequisite: Data Persistence

The AniMiKyoku backend is **stateful**. When you upload a poster and confirm its title, the application saves the new data to disk (`data/index.faiss`, `data/posters.json`, etc.). This allows for faster, RAG-based identification in the future.

Because of this, **the free tier on Render is not sufficient for the backend to function correctly.** Free services use an ephemeral filesystem, meaning any new data you ingest will be **permanently deleted** every time the service restarts.

**To make the application work as intended, you MUST use a [Render Disk](httpss://render.com/docs/disks) to provide persistent storage.** Render Disks are a paid feature. See the alternative option below for a free alternative.

---

## Part 1: Backend Deployment (Render)

We will deploy the Python backend as a Docker container on Render.

### Step 1: Sign Up and Create a Web Service

1. Create an account on [Render](httpss://render.com).
2. From the dashboard, click **New +** and select **Web Service**.
3. Connect your GitHub/GitLab account and select the `AniMiKyoku` repository.

### Step 2: Configure the Render Service

Fill in the service details as follows:

- **Name:** `animikyoku-backend` (or your preferred name).
- **Region:** Choose a region close to you.
- **Branch:** `main` (or your primary branch).
- **Runtime:** Select **Docker**.

Render will automatically detect the `Dockerfile` in your `backend` directory.

- **Root Directory:** `backend`
  *This is crucial. It tells Render to run the Docker build from within the `backend` folder.*

### Step 3: Add a Persistent Disk

1. Scroll down to the **Advanced** section and click **Add Disk**.
2. Configure the disk:
   - **Name:** `data-disk` (or similar).
   - **Mount Path:** `/app/data`
     *This path tells Render to make the persistent disk available inside the container at `/app/data`.*
   - **Size:** Start with `1 GB`. You can resize it later if needed.

### Step 4: Add Environment Variables

1. In the service settings, go to the **Environment** tab.
2. Add the following secret files and environment variables:

   - **Secret File**:

     - **Key**: `GEMINI_API_KEY`
     - **Value**: Paste your Google Gemini API key.
   - **Environment Variables**:

     - **Key**: `DATA_DIR_PATH`
     - **Value**: `/app/data`
       *This tells the Python application to use the mounted disk for its data.*
     - **Key**: `ALLOW_ORIGINS`
     - **Value**: `https://your-frontend-url.vercel.app` (We will get this URL in Part 2, for now you can use a placeholder like `http://localhost:5173`).
     - **Key**: `PYTHON_VERSION`
     - **Value**: `3.12` (or the version specified in `environment.yml`)

### Step 5: Deploy

1. Click **Create Web Service** at the bottom of the page.
2. The first build will take a long time (15-25 minutes) as it needs to install all the Conda dependencies (`pytorch`, `faiss-cpu`, etc.) into the Docker image.
3. Once deployed, Render will provide you with a public URL for your backend (e.g., `httpss://animikyoku-backend.onrender.com`). Copy this URL.

---

## Part 2: Frontend Deployment (Vercel)

We will deploy the React frontend on Vercel.

### Step 1: Sign Up and Create a Project

1. Create an account on [Vercel](httpss://vercel.com).
2. From the dashboard, click **Add New...** and select **Project**.
3. Connect your GitHub/GitLab account and import the `MiKyoku` repository.

### Step 2: Configure the Vercel Project

Vercel is excellent at auto-detection. It should recognize that you have a Vite project.

1. **Framework Preset:** Ensure it is set to **Vite**.
2. Expand the **Root Directory** section and select **frontend**.

Vercel will automatically configure the Build Command (`npm run build`) and Output Directory (`dist`).

### Step 3: Add Environment Variable

1. In the project settings, go to the **Environment Variables** section.
2. Add the following variable:
   - **Key**: `VITE_BACKEND_URL`
   - **Value**: Paste the URL of your Render backend service (e.g., `httpss://animikyoku-backend.onrender.com`).

### Step 4: Deploy

1. Click **Deploy**.
2. Vercel will build and deploy your frontend, providing you with a public URL (e.g., `httpss://animikyoku-frontend.vercel.app`).

---

## Part 3: Final Configuration

The last step is to allow the frontend to communicate with the backend.

1. Go back to your backend service on **Render**.
2. Navigate to the **Environment** tab.
3. Update the `ALLOW_ORIGINS` environment variable with your actual Vercel frontend URL.
   - **Key**: `ALLOW_ORIGINS`
   - **Value**: `httpss://your-frontend-url.vercel.app` (e.g., `httpss://animikyoku-frontend.vercel.app`)
4. Render will automatically restart the service with the new environment variable.

**Your application is now live!** You can access it via your Vercel URL.

---

---

## Alternative Backend Host: Fly.io (Free Tier with Persistent Disk)

If you are looking for a free alternative to Render that supports persistent storage, **Fly.io** is an excellent choice. Their free tier includes a small persistent volume, which is exactly what this application needs.

The `Dockerfile` already created in the `backend` directory will work perfectly with Fly.io.

### Step 1: Install `flyctl`

First, you need to install the Fly.io command-line tool, `flyctl`. Follow the official instructions for your operating system: [Install flyctl](httpss://fly.io/docs/hands-on/install-flyctl/).

### Step 2: Log In and Launch

1. Open your terminal.
2. Log in to Fly:
   ```sh
   fly auth login
   ```
3. Navigate into the `backend` directory of your project:
   ```sh
   cd backend
   ```
4. Launch the app. This command will analyze your project and suggest a configuration.
   ```sh
   fly launch
   ```

### Step 3: Answer the Launch Prompts

`fly launch` will ask you a series of questions:

- **App Name:** Choose a unique name (e.g., `animikyoku-backend`).
- **Region:** Select a region near you.
- **Set up a Postgresql database now?** No.
- **Set up a Redis database now?** No.
- **Create a persistent volume for your app?** Yes.
  - **Size in GB:** `1`
  - **Path for volume:** `/app/data`
  - **Name for volume:** `data`
- **Would you like to deploy now?** No. We need to set secrets first.

This will create a `fly.toml` configuration file in your `backend` directory.

### Step 4: Set Secrets

Now, set the required environment variables as secrets in Fly.io.

```sh
fly secrets set "GEMINI_API_KEY=your_google_gemini_key"
fly secrets set "DATA_DIR_PATH=/app/data"
fly secrets set "ALLOW_ORIGINS=https://your-frontend-url.vercel.app" # Use your Vercel URL here
```

### Step 5: Deploy the Application

Now you are ready to deploy.

```sh
fly deploy
```

Fly.io will build the Docker image, provision the volume, and deploy your application. Once it's finished, it will give you a public URL (e.g., `httpss://animikyoku-backend.fly.dev`).

### Step 6: Final Configuration

- Update the `VITE_BACKEND_URL` in your Vercel frontend project to point to your new Fly.io backend URL.
- If you used a placeholder for `ALLOW_ORIGINS`, make sure to update it with your real Vercel URL using the `fly secrets set` command and re-deploy.
