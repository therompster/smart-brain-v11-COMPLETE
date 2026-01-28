# BillBrain Unified

**Email triage system that detects bills AND actionable tasks, with Second Brain integration.**

## Features

- 📧 **Email Scanning**: Fetches emails via Gmail API
- 💵 **Bill Detection**: Identifies financial obligations (utilities, subscriptions, invoices)
- ✅ **Action Detection**: Identifies emails requiring a response or task
- 🧠 **Second Brain Sync**: Pushes approved actions to Smart Second Brain as tasks
- 🎯 **ADHD-Friendly**: Includes first steps, time estimates, and priority levels

## Architecture

```
Email → LLM Classification → Bill | Action | Ignore
                                ↓        ↓
                           BillBrain   Second Brain
                           (track $)   (track tasks)
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Gmail API Setup

1. Create project at https://console.cloud.google.com
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download as `credentials.json` in this folder
5. Run once to authenticate: `python connectors/gmail_connector.py`

### 3. Configure Ollama

```bash
ollama pull qwen2.5:14b
```

### 4. Set Second Brain Path

Edit `connectors/second_brain_sync.py` line 14:
```python
SECOND_BRAIN_DB = "../smart-brain-webui/data/smart_brain.db"
```

### 5. Run

```bash
python main.py
```

Open http://localhost:8001

## Usage

### Web UI

1. **Scan Emails**: Click to fetch and classify new emails
2. **Bills Tab**: Approve/ignore detected bills, mark as paid
3. **Actions Tab**: Approve/ignore action items
4. **Sync to Second Brain**: Push approved actions as tasks

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ingest` | POST | Scan emails |
| `/api/bills` | GET | List bills |
| `/api/bills/{id}/approve` | POST | Approve bill |
| `/api/bills/{id}/paid` | POST | Mark paid |
| `/api/actions` | GET | List actions |
| `/api/actions/{id}/approve` | POST | Approve action |
| `/api/actions/sync` | POST | Sync to Second Brain |
| `/api/stats` | GET | Get counts |

## Classification Logic

### Bills (financial tracking)
- Utility statements (electric, gas, water)
- Subscription renewals
- Invoices and payment requests
- Credit card statements
- Insurance premiums

### Actions (task tracking)
- Meeting requests
- Questions requiring response
- Document review requests
- Follow-up requests
- Deadline notifications

### Ignored
- Marketing emails
- Newsletters
- Order confirmations (no action needed)
- Automated notifications
- Spam

## Database Schema

### BillEntity / BillInstance
Full financial tracking with vendor normalization, amounts, due dates, autopay status.

### ActionItem
- `action_required`: What needs to be done
- `sender_name`: Who sent it
- `priority`: high/medium/low
- `domain`: work/personal/admin
- `first_step`: ADHD-friendly 2-minute starter
- `estimated_minutes`: Time estimate
- `second_brain_task_id`: Linked task ID after sync

## Integration with Second Brain

When you click "Sync to Second Brain":
1. All APPROVED actions are pushed to Second Brain's tasks table
2. Each action becomes a task with:
   - Text: action + sender context
   - Action: First step (verb-first)
   - Priority: Mapped from action priority
   - Domain: Mapped to Second Brain domains
   - Estimated duration
3. Action status changes to SYNCED
4. Task ID is stored for reference

## File Structure

```
billbrain-unified/
├── main.py              # FastAPI app
├── models.py            # SQLAlchemy models
├── llm_client.py        # Ollama integration
├── orchestrator.py      # Ingestion pipeline
├── index.html           # Web UI
├── connectors/
│   ├── gmail_connector.py
│   └── second_brain_sync.py
├── requirements.txt
└── README.md
```
