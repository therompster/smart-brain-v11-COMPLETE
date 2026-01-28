# Smart Second Brain - Complete Handoff Package v13.1

**Date:** January 27, 2026
**Version:** v13.1 (Hierarchy + Strict Classification)
**Status:** Functional with brain dump processor enhancements

---

## WHAT'S NEW IN V13.1

### Stricter Project Classification
- Headers like "TIP AI:" now treated as context, not new projects
- "project" type reserved for explicit declarations only
- Reduces over-creation of project entries

### Project Hierarchy Detection
- Detects parent-child relationships (e.g., "ECMP AI" under "ECMP")
- Separate from consolidations (which merge duplicates)
- Sets `parent_project_id` in database when applied

### Semantic Item-to-Project Assignment
- Items matched to existing projects by semantic similarity
- Only assigns when confidence > 0.6
- Adds `assigned_project`, `assignment_confidence` fields

### Database
- Added `parent_project_id` column to projects table
- Enables project hierarchies/nesting

### UI Updates  
- Consolidate step now has two sections: Merge Duplicates & Project Hierarchy
- Visual: child → under → parent with confidence badges
- Done step shows hierarchy count

---

## WHAT WAS IN V13

### Brain Dump Item Type Classification
- Items now classified into 7 types: task, note, idea, question, decision, reference, project
- Signal word detection for automatic classification
- Each type stored in appropriate table with metadata

### Project Consolidation
- Detects duplicate/similar project names (e.g., "TIP AI", "tip.ai", "TIP AI stuff")
- Suggests merge/rename operations
- UI step for reviewing consolidation suggestions before save
- Applies consolidations when saving items

### UI Updates
- Items displayed grouped by type with color-coded badges
- Summary shows counts per item type
- Icons: ✅ Task, 📝 Note, 💡 Idea, ❓ Question, ⚖️ Decision, 🔗 Reference, 📁 Project

### Database
- Added `questions` table for open questions from brain dumps
- Added `decisions` table for tracking decisions

### API Endpoints
- `GET /api/questions` - List questions (filterable by status, domain)
- `POST /api/questions/{id}/answer` - Answer a question
- `GET /api/decisions` - List decisions (filterable by domain)

---

## WORKFLOW: Brain Dump Processing

1. **Input** - User pastes messy notes
2. **Analyze** - LLM classifies each item by type, detects projects/people
3. **Clarify** (if needed) - User answers questions about ambiguous items
4. **Consolidate** (if needed) - User reviews project merge + hierarchy suggestions
5. **Review** - User sees all items grouped by type, can select projects to create
6. **Save** - Items routed to appropriate tables, consolidations & hierarchies applied
7. **Done** - Summary of saved items shown

---

## SYSTEM ARCHITECTURE

### Tech Stack
- **Backend:** FastAPI (Python 3.11), SQLite, ChromaDB
- **Frontend:** Svelte + Vite, TailwindCSS
- **AI:** Ollama (local LLMs)
  - Task extraction: deepseek-r1:14b
  - Entity recognition: qwen2.5:32b
  - Routing: qwen2.5:14b
  - Clustering: qwen2.5:14b
  - Fallback: llama3.1:8b

### Database Schema
**Core Tables:**
- `notes` - Note storage
- `tasks` - Extracted tasks with metadata
- `projects` - Project definitions
- `questions` - Open questions from brain dumps
- `decisions` - Tracked decisions
- `user_profile` - User profile and onboarding state
- `user_domains` - Dynamic domains from profile

**Learning Tables:**
- `routing_confidence` - Learned routing accuracy
- `entity_confidence` - Known people/projects
- `learned_thresholds` - Adaptive thresholds
- `learned_weights` - Priority weight learning
- `completion_patterns` - Energy pattern learning

### File Structure
```
smart-brain-webui/
├── src/
│   ├── api.py                    # FastAPI endpoints
│   ├── config.py                 # Settings
│   ├── llm/
│   │   └── ollama_client.py      # Multi-model LLM client
│   ├── models/
│   │   └── workflow_state.py     # Data models
│   ├── services/
│   │   ├── brain_dump_service.py        # Brain dump parsing + item classification
│   │   ├── project_service.py           # Project management
│   │   ├── confidence_service.py        # Routing confidence tracking
│   │   ├── daily_planning_service.py    # AI daily plans
│   │   ├── domain_service.py            # Dynamic domains
│   │   ├── energy_pattern_service.py    # Peak productivity learning
│   │   └── ...
│   └── storage/
│       └── file_system.py        # Vault file management
├── ui/
│   └── src/
│       ├── App.svelte            # Main app
│       ├── BrainDumpProcessor.svelte  # Brain dump UI with item types
│       ├── NoteEditor.svelte     # Note editing
│       ├── DailyPlan.svelte      # Today view
│       └── ...
├── scripts/
│   └── init_database.py          # Database initialization + migrations
└── vault/                        # Markdown notes storage
```

---

## SETUP INSTRUCTIONS

### Prerequisites
- Python 3.11
- Node.js 18+
- Conda
- Ollama running locally

### Install Models
```bash
ollama pull deepseek-r1:14b
ollama pull qwen2.5:32b
ollama pull qwen2.5:14b
ollama pull llama3.1:8b
```

### Backend Setup
```bash
conda create -n brain python=3.11
conda activate brain
pip install -r requirements.txt
python scripts/init_database.py
python -m src.main
# Runs on http://localhost:8000
```

### Frontend Setup
```bash
cd ui
npm install
npm run dev
# Runs on http://localhost:5173
```

### Database Migration (for existing installs)
```python
from scripts.init_database import add_questions_decisions_tables
add_questions_decisions_tables()
```

---

## API ENDPOINTS

### Brain Dump Processing
- `POST /api/brain-dump/analyze` - Analyze brain dump, returns items with types
- `POST /api/brain-dump/save` - Save items to database
- `POST /api/brain-dump/suggest-projects` - Get project suggestions
- `POST /api/brain-dump/consolidate-projects` - Apply project consolidations

### Questions & Decisions
- `GET /api/questions` - List questions
- `POST /api/questions/{id}/answer` - Answer a question
- `GET /api/decisions` - List decisions

### Notes & Tasks
- `POST /api/notes/process` - Process note for classification
- `POST /api/notes` - Save note
- `GET /api/notes` - List notes
- `GET /api/tasks` - List tasks
- `POST /api/tasks/{id}/complete` - Complete task

### Projects
- `GET /api/projects?domain=...` - List projects for domain
- `POST /api/projects` - Create project
- `PUT /api/projects/{id}` - Update project

### Planning
- `GET /api/plan/daily` - Get daily plan (3-5 tasks)

---

## BRAIN DUMP SERVICE

### Item Type Detection
The service uses signal words to classify items:

| Type | Signal Words |
|------|-------------|
| Task | "need to", "should", "must", "schedule", "create", "fix", "talk to" |
| Note | "is", "has", "there's a", facts, descriptions |
| Idea | "could", "might", "what if", "maybe", "consider" |
| Question | "?", "how", "what", "why", "find out", "figure out" |
| Decision | "decided", "will", "going to", "chosen", "agreed" |
| Reference | URLs, document names, "see:", "ref:" |
| Project | Initiative names, "project:", new workstreams |

### Project Consolidation
Detects similar projects using:
1. Fuzzy string matching
2. Case-insensitive comparison
3. Suffix stripping ("stuff", "tasks", "items")
4. Abbreviation expansion

---

## FEATURES STATUS

### ✅ Complete
- Note creation with AI classification
- Task extraction from notes
- Daily planning (3-5 tasks)
- Brain dump processing with item types
- Project consolidation suggestions
- Clarification questions for ambiguous items
- Multi-model LLM support

### 🔄 In Progress
- Questions/Decisions views in UI
- Project management UI

### ❌ Not Started
- Gamification (XP, streaks, badges)
- Evening review workflow
- Energy-aware task suggestions
- Time tracking

---

## TESTING CHECKLIST

### Brain Dump Flow
- [ ] Paste messy notes
- [ ] Items classified by type correctly
- [ ] Ambiguous items get clarification step
- [ ] Project consolidation suggestions shown
- [ ] Items saved to correct tables
- [ ] Projects created from suggestions

### Database
- [ ] Questions table exists
- [ ] Decisions table exists
- [ ] Items have correct metadata

---

## VERSION HISTORY

- **v1-v3:** Web UI, note editor, task extraction
- **v4-v6:** Daily planning, profile onboarding
- **v7-v10:** Adaptive learning, multi-model LLM
- **v11:** Dynamic domains, learned thresholds
- **v12:** Brain dump processor, project suggestions
- **v13:** Item type classification, project consolidation
