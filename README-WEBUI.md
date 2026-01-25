# Smart Second Brain - Web UI Edition

Local-first AI note-taking with auto-organization, task extraction, and intelligent linking.

## Quick Start

### Backend Setup

```bash
# 1. Pull Ollama models
ollama pull qwen2.5:14b
ollama pull llama3.1:8b

# 2. Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Initialize database
cp .env.example .env
python scripts/init_database.py

# 4. Start backend
python src/api.py
```

Backend runs on http://localhost:8000

### Frontend Setup

```bash
cd ui
npm install
npm run dev
```

Frontend runs on http://localhost:5173

## Usage

1. Open http://localhost:5173
2. Click "New Note"
3. Start writing
4. AI auto-classifies domain (Marriott/Konstellate/Personal/etc)
5. Hit Save → note organized in vault

## Features

**Write notes in UI:**
- Real-time domain classification
- Auto-linking to related notes
- Keyword extraction
- Markdown preview

**Auto-organization:**
- Routes to PARA domains
- Suggests note type (Project/Area/Note)
- Writes to vault/[domain]/[type]/
- Stores in SQLite

**Beautiful UI:**
- Dark theme optimized for focus
- Color-coded domains
- Markdown editor with preview
- Minimal, fast interface

## Architecture

```
┌─────────────┐         ┌──────────────┐
│  Svelte UI  │  ────▶  │  FastAPI     │
│  Port 5173  │  ◀────  │  Port 8000   │
└─────────────┘         └──────────────┘
                               │
                        ┌──────┴──────┐
                        │   Ollama    │
                        │  qwen2.5    │
                        └──────┬──────┘
                               │
                        ┌──────┴──────┐
                        │   Storage   │
                        │ SQLite +    │
                        │ Vault files │
                        └─────────────┘
```

## API Endpoints

- `POST /api/notes/process` - Classify note without saving
- `POST /api/notes` - Save note
- `GET /api/notes` - List all notes
- `GET /api/notes/{id}` - Get single note
- `GET /api/domains` - List PARA domains

## Next: Phase 2

- Task extraction from notes
- Task deduplication
- Smart linking (wikilinks)
- Daily planning view
