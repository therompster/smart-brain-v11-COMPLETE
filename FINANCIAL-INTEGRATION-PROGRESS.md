# Smart Second Brain - Financial Integration Progress Log

**Started:** January 27, 2026
**Goal:** Unified productivity + financial tracking system with email triage

---

## ARCHITECTURE VISION

```
Smart Second Brain (Unified)
│
├── 📋 WORK
│   ├── Marriott (tasks, projects, notes)
│   └── Konstellate (tasks, projects, notes)
│
├── 👤 PERSONAL
│   └── Tasks, notes
│
├── 📚 LEARNING
│   └── Notes, resources
│
└── 💰 FINANCIAL (new module)
    ├── Bills (one-time: electric, medical, invoices)
    ├── Subscriptions (recurring: Netflix, Spotify, gym)
    ├── Loans (mortgage, car, student - with amortization)
    └── Transactions (bank import via CSV/Plaid)
```

---

## TODO LIST

### Phase 1: Email → Task Pipeline ✅ COMPLETE
- [x] 1.1 Create `/api/tasks/from-email` endpoint in Smart Second Brain
- [x] 1.2 Create `email_task_service.py` with deduplication logic
- [x] 1.3 Add database migration for metadata column
- [x] 1.4 Update BillBrain connector to use API instead of direct DB
- [ ] 1.5 Test end-to-end (manual - on your machine)

### Phase 2: Financial Domain in Smart Second Brain ✅ COMPLETE
- [x] 2.1 Add "financial" domain to Smart Second Brain
- [x] 2.2 Create database tables: bills, subscriptions, loans, loan_payments, transactions
- [x] 2.3 Create financial_service.py with CRUD operations
- [x] 2.4 Create Financial API endpoints (11 endpoints)
- [x] 2.5 Create Financial dashboard UI component
- [x] 2.6 Add bill sync to BillBrain connector

### Phase 3: Loan Tracking
- [ ] 3.1 Loan entity model (principal, rate, term, start date)
- [ ] 3.2 Amortization calculator
- [ ] 3.3 Payment tracking (actual vs scheduled)
- [ ] 3.4 Remaining balance / payoff date projections
- [ ] 3.5 Loan dashboard with charts

### Phase 4: Bank Transaction Import
- [ ] 4.1 CSV/OFX parser for bank exports
- [ ] 4.2 Transaction categorization (LLM-based)
- [ ] 4.3 Auto-match transactions to bills/subscriptions
- [ ] 4.4 Spending insights / monthly summary
- [ ] 4.5 (Optional) Plaid integration for live sync

### Phase 5: Polish & Integration
- [ ] 5.1 Unified dashboard (work + financial summary)
- [ ] 5.2 Alerts: overdue bills, upcoming payments
- [ ] 5.3 Mobile-friendly views
- [ ] 5.4 Budget tracking

---

## COMPLETED

### 2026-01-27: Phase 1.1-1.3 - Email Task API

**Files Created/Modified in Smart Second Brain:**

1. `src/services/email_task_service.py` (NEW)
   - `EmailTaskService` class
   - `create_task_from_email()` - main entry point
   - `_check_duplicate()` - semantic similarity check against existing tasks
   - `_route_to_domain()` - uses route_service or domain_hint
   - `_insert_task()` - creates task with email metadata
   - `get_email_tasks()` - list tasks from email sources

2. `src/api.py` (MODIFIED)
   - Added `EmailTaskCreate` request model
   - Added `EmailTaskResponse` response model
   - Added `EmailTaskBatchCreate` / `EmailTaskBatchResponse` for batch ops
   - `POST /api/tasks/from-email` - single task creation
   - `POST /api/tasks/from-email/batch` - batch creation
   - `GET /api/tasks/from-email` - list email-sourced tasks

3. `scripts/init_database.py` (MODIFIED)
   - Added `add_email_task_support()` migration
   - Adds `metadata JSON` column to tasks table

**API Contract:**
```
POST /api/tasks/from-email
{
  "action": "Review contract and sign",
  "sender": "legal@company.com",
  "subject": "Contract for review",
  "priority": "high",
  "domain_hint": "work",
  "deadline": "2026-02-01",
  "context": "NDA for new vendor",
  "first_step": "Read section 3 liability clause",
  "estimated_minutes": 30,
  "source_email_id": "msg_abc123"
}

Response:
{
  "task_id": 42,
  "was_duplicate": false,
  "duplicate_of": null,
  "assigned_domain": "work/marriott",
  "message": "Task created successfully"
}
```

### 2026-01-26: BillBrain Unified v1
- [x] Enhanced LLM client with 3-way classification (BILL/ACTION/IGNORE)
- [x] ActionItem database model with ADHD fields
- [x] Orchestrator routing pipeline
- [x] Web UI with Bills/Actions tabs
- [x] Basic Second Brain sync (direct DB - TO BE REPLACED)

**Output:** `/mnt/user-data/outputs/billbrain-unified.tar.gz`

---

## NEXT UP: Phase 3 - Loan Amortization UI

- Detailed schedule view with payment breakdown
- Extra payment calculator ("what if I pay $X extra?")
- Payoff projection charts
- Compare to original schedule

---

## FILE LOCATIONS

| Component | Location |
|-----------|----------|
| Smart Second Brain | `/home/claude/smart-brain-webui/` |
| BillBrain Unified | `/home/claude/billbrain-unified/` |
| This Progress Log | `/home/claude/FINANCIAL-INTEGRATION-PROGRESS.md` |

---

## NOTES

### Banking API Options
| Option | Cost | Notes |
|--------|------|-------|
| Plaid | Free dev (100 items) | Best docs, most banks |
| CSV/OFX Import | Free | Manual but works everywhere |
| SimpleFIN | ~$1.50/mo | Privacy-focused |

### Key Decisions
- Email tasks go through Smart Brain API (not direct DB insert)
- Bills/Subscriptions/Loans are SEPARATE from regular tasks
- Financial domain is parallel to work domains, not nested under them
