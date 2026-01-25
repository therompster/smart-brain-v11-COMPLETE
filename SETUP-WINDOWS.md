# Smart Second Brain - Windows Setup

## Prerequisites
- Conda (Anaconda/Miniconda)
- Ollama for Windows
- Node.js 18+

## Setup

### Backend
```bash
# Pull models
ollama pull qwen2.5:14b
ollama pull llama3.1:8b

# Create conda environment
conda create -n smartbrain python=3.11
conda activate smartbrain

# Install dependencies
pip install -r requirements.txt

# Initialize
copy .env.example .env
python scripts\init_database.py

# Start backend
python src\api.py
```

### Frontend
```bash
cd ui
npm install
npm run dev
```

Open http://localhost:5173

## Usage
1. Write notes in UI
2. AI auto-classifies domain
3. Save → organized in vault

## Troubleshooting

**"Ollama connection failed"**
- Start Ollama Desktop app
- Or run: `ollama serve`

**Import errors**
- Ensure conda env activated: `conda activate smartbrain`

**Port conflicts**
- Backend: Edit `src/api.py` line `uvicorn.run(..., port=8000)`
- Frontend: Edit `ui/vite.config.js` line `port: 5173`
