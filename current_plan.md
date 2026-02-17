# Current Project Status & Transfer Plan

## 📌 Context Summary (As of Feb 11, 2026)
We have been working on **QBank V2**, specifically focusing on the Teacher/Admin experience and the robustness of the question generation pipeline.

### Recent Accomplishments
- **Job Generation**: Implemented `QBANK_V2_QUEUE_MODE=auto` which allows generating questions even if Redis is not running (inline fallback).
- **Library UX**: Added a `difficulty` column to the database and frontend filters. Replaced slow sequential fetching with a fast `/v2/qbank/items/search` endpoint.
- **Frontend Restoration**: Fixed the Live Feed so it shows previously generated items when reopening a job.
- **Rendering**: Enhanced `MathRenderer.tsx` for better handling of mixed inline/block LaTeX.

### Current State
- **Backend**: Python (FastAPI/main_v2_local.py).
- **Frontend**: Vite/React/TypeScript.
- **Database**: Supabase (PostgreSQL).
- **Worker**: `question_banks.v2.worker` handles the heavy lifting.

## 🚀 Next Steps (For the Laptop)
1. **Frontend Polish**: Ensure the new "Review" button on Job History page correctly redirects to the detailed view.
2. **Data Validation**: Monitor token usage/cost calculations in the Job Status page to ensure accuracy for large batches.
3. **Deployment Prep**: Verify if the `auto` queue mode is suitable for the staging environment or if Redis should be enforced there.

## 🛠️ Local Setup Commands
```bash
# Terminal 1: API
python main_v2_local.py

# Terminal 2: Worker
python -m question_banks.v2.worker

# Terminal 3: Frontend
cd frontend && npm run dev
```

## 🔋 Transfer Checklist
- [ ] Push code to a remote (e.g., `git remote add origin <url> && git push -u origin main`).
- [ ] Ensure `.env` is synchronized (manually or via secure vault).
- [ ] On laptop: `git pull` -> `pip install -r requirements.txt` -> `cd frontend && npm install`.
- [ ] Drag this file into your first laptop chat to resume context.
