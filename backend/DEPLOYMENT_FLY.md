# AniMiKyoku Deployment Guide - Fly.io

Complete guide for deploying AniMiKyoku on Fly.io with persistent storage.

## Architecture Overview

- **Backend:** Deployed as a Docker container on Fly.io
- **Data Storage:** Fly Volume for persistent FAISS indices, embeddings, and poster images
- **Initial Data:** Pre-built indices and posters are included in the Docker image
- **User Uploads:** Persist on the volume and survive restarts/redeployments

---

## Prerequisites

1. **Fly.io Account:** Sign up at [fly.io](https://fly.io)
2. **Fly CLI:** Install from [fly.io/docs/flyctl/install](https://fly.io/docs/flyctl/install/)
3. **Pre-built Data:** Ensure you have run the following scripts locally:

   ```bash
   # Generate CLIP embeddings for all posters
   python backend/scripts/build_embeddings.py

   # Build FAISS index from embeddings
   python backend/scripts/build_faiss_index.py
   ```

   This creates:- `data/posters.json` (with embeddings)

   - `data/index.faiss`
   - `data/index.mapping.json`

---

## Step 1: Create the Volume

Create a persistent volume to store your data (posters, embeddings, FAISS index).

```bash
# Create 1GB volume in your primary region (fra = Frankfurt)
fly volumes create data --size 1 --region fra
```

**Note:** The volume name must match the `source` in `fly.toml` (`[mounts]` section).

---

## Step 2: Set Environment Variables

Add your API keys and configuration as secrets:

```bash
# Set Gemini API key
fly secrets set GEMINI_API_KEY="your-gemini-api-key-here"

# Set CORS origins (add your frontend URL)
fly secrets set ALLOW_ORIGINS="https://mi-kyoku.vercel.app"
```

**Environment Variables Explained:`**

- `GEMINI_API_KEY`: Required for AI-based anime identification when RAG doesn't have a match
- `ALLOW_ORIGINS`: Comma-separated list of allowed frontend origins for CORS
- `DATA_DIR_PATH`: Already set in `fly.toml` to `/app/data` (points to the mounted volume)

---

## Step 3: Initial Deployment

Deploy your application. The first deployment will:

1. Build the Docker image with your pre-built data
2. Copy the data to the volume on first run
3. Start the backend server

```bash
# Login to Fly (if not already)
fly auth login

# Deploy (first time will take ~10-15 minutes due to PyTorch/FAISS installation)
fly deploy
```

**What happens during build:**

- Docker installs Python, PyTorch (CPU version), FAISS, CLIP, and all dependencies
- Your `data/` folder (with posters, embeddings, indices) is copied into the image
- On first run, if the volume is empty, the data will be available from the image

---

## Step 4: Verify Deployment

Check if your app is running:

```bash
# Check deployment status
fly status

# View logs
fly logs

# Open in browser
fly open
```

Expected log output:

```
[STARTUP] AniMiKyoku Backend Starting...
[OK] RAG vector store initialized: 235 vectors loaded
[OK] RAG System: OPERATIONAL
     - Index vectors: 235
     - ID mappings: 235
     - Metadata entries: 235
```

---

## Step 5: Test the API

Test the identification endpoint:

```bash
# Health check
curl https://animikyoku.fly.dev/

# Test with an image
curl -X POST https://animikyoku.fly.dev/api/identify \
  -H "Content-Type: multipart/form-data" \
  -F "image=@path/to/test/poster.jpg"
```

---

## Data Persistence Explained

### How the Volume Works

1. **First Deployment:**

   - Volume is empty
   - Docker image contains `data/` folder with pre-built indices
   - App starts and uses the data from the image (available at `/app/data`)
2. **When User Uploads a New Poster:**

   - App saves the poster to `/app/data/posters/new_poster.jfif`
   - App updates `/app/data/posters.json` with new embedding
   - App rebuilds `/app/data/index.faiss` with the new vector
   - All changes are written to the **volume** (persist across restarts)
3. **After Redeployment:**

   - Docker image rebuilds with your original data
   - **Volume still contains user uploads** (they don't get overwritten)
   - App loads the volume data, which includes both:
     - Original posters (from image)
     - User-uploaded posters (from volume)

### Important Notes

- ✅ **User uploads persist** across restarts and redeployments
- ✅ **No need to rebuild indices on production** - they're pre-built locally
- ⚠️ **If you delete the volume**, all user uploads are lost (backup important!)
- ⚠️ **Volume is per-machine** - if you scale to multiple machines, they don't share the volume

---

## Updating Pre-built Data

If you add more posters locally and want to update production:

```bash
# 1. Build embeddings locally
python backend/scripts/build_embeddings.py

# 2. Build FAISS index locally
python backend/scripts/build_faiss_index.py

# 3. Deploy (this copies the updated data/ folder to the image)
fly deploy
```

**The volume will merge:**

- New posters from the image
- Existing user uploads from the volume

---

## Troubleshooting

### Volume Not Mounting

Check that the volume name matches `fly.toml`:

```bash
fly volumes list
```

Should show a volume named `data` in region `fra`.

### Data Not Persisting

1. Check the DATA_DIR_PATH environment variable:

   ```bash
   fly ssh console
   echo $DATA_DIR_PATH
   # Should output: /app/data
   ```
2. Verify volume is mounted:

   ```bash
   fly ssh console
   ls -la /app/data
   # Should show: posters/, index.faiss, posters.json, etc.
   ```

### Out of Space

Resize the volume:

```bash
fly volumes extend <volume-id> --size 2
```

### RAG Not Working

Check logs for initialization errors:

```bash
fly logs | grep "RAG"
```

Expected output:

```
[OK] RAG vector store initialized: 235 vectors loaded
[OK] RAG System: OPERATIONAL
```

---

## Scaling Considerations

### Single Machine (Current Setup)

- ✅ Simple, cost-effective
- ✅ Data persists on one volume
- ⚠️ No redundancy

### Multiple Machines (Future)

If you need to scale horizontally:

1. Use a shared storage service (e.g., S3, Cloudflare R2)
2. Or use a single "data" machine + read-only API machines
3. Or rebuild indices on each machine startup (slower)

For now, single machine is sufficient for your use case.

---

## Cost Estimate

- **VM:** ~$2-3/month (1GB RAM, shared CPU, auto-stop when idle)
- **Volume:** ~$0.15/GB/month (1GB = $0.15/month)
- **Bandwidth:** First 100GB free

**Total:** ~$2-3/month

---

## Commands Cheat Sheet

```bash
# Deploy
fly deploy

# Check status
fly status

# View logs (live)
fly logs

# SSH into machine
fly ssh console

# List volumes
fly volumes list

# Set secrets
fly secrets set KEY=value

# Scale memory
fly scale memory 2048

# Stop machine (save costs)
fly machine stop

# Start machine
fly machine start

# Destroy app (careful!)
fly apps destroy animikyoku
```

---



## Support

- Fly.io Docs: [fly.io/docs](https://fly.io/docs)
- Fly.io Community: [community.fly.io](https://community.fly.io)
- Volume Guide: [fly.io/docs/volumes](https://fly.io/docs/volumes/overview/)
