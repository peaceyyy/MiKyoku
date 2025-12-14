# Environment Setup Instructions

## Windows + GPU Setup (Recommended)

### Option 1: Conda (Recommended for GPU/Windows)

```powershell
# Create environment from YAML
conda env create -f environment.yml

# Activate
conda activate anime-id

# Verify GPU availability
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

### Option 2: Conda + Manual (if YAML fails)

```powershell
# Create base environment
conda create -n anime-id python=3.10 -y
conda activate anime-id

# Install PyTorch with CUDA 12.1 (adjust version to match your drivers)
conda install pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia -y

# Install FAISS
conda install faiss-cpu -c conda-forge -y

# Install Python packages
pip install -r backend/requirements.txt
```

### Option 3: venv + pip (CPU-only or manual CUDA)

```powershell
# Create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install PyTorch (CPU version)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# OR install GPU version (match your CUDA)
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install FAISS
pip install faiss-cpu

# Install other packages
pip install -r backend/requirements.txt
```

---

## Verify Installation

```powershell
python -c "import torch; import open_clip; import faiss; print('✅ All imports successful')"
```

---

## Quick Start Commands

```powershell
# Normalize filenames (already done)
python backend/scripts/normalize_filenames.py --source poster_db --dest posters --output data/posters.json --apply

# Build embeddings (after embedder is implemented)
python backend/scripts/build_embeddings.py --posters posters --metadata data/posters.json --output data/embeddings.npz

# Build FAISS index (after vector store is implemented)
python backend/scripts/build_faiss_index.py --embeddings data/embeddings.npz --output data/index.faiss

# Start FastAPI backend (after router is implemented)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### CUDA version mismatch
```powershell
nvidia-smi  # Check CUDA version
# Then install matching pytorch-cuda version
```

### Import errors
```powershell
pip list | grep -E "torch|faiss|open-clip"
```

### GPU memory issues
- Reduce batch size in config
- Use `torch.cuda.empty_cache()` between operations
- Consider mixed precision training
