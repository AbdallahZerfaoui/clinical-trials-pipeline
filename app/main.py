from fastapi import FastAPI, HTTPException
# from .db import SessionLocal
from app.models import ClinicalTrial
from .pipeline import Pipeline

app = FastAPI(title="ClinicalTrials.gov PoC")

welcome_message = "As a demo of exactly the kind of automation I’d build, \
I’ve created an Active Oncology Trial Alerts endpoint. \
In one weekend I’ll show you an API that pulls only Phase II/III recruiting trials \
updated in the last 7 days in Europe, computes a simple urgency score, and exposes \
it via /trials/active‑oncology. \
It’s live at [PoC URL] and the full Terraform + Python code is at [GitHub link]."

@app.on_event("startup")
def startup_event():
    # optionally run ingestion on start
    pass

@app.get("/")
def read_root():
    """
    Root endpoint that returns a welcome message.
    """
    return {"message": welcome_message}

@app.post("/run")
def trigger_run(condition: str = "cardiology", days: int = 7):
    try:
        pipeline = Pipeline()
        pipeline.run_ingestion(condition=condition, days=days)
        return {"status": "ingested"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summary")
def get_summary():
    pipeline = Pipeline()
    session = pipeline.session
    total = session.query(ClinicalTrial).count()
    by_phase = {
        phase: session.query(ClinicalTrial).filter_by(phase=phase).count()
        for phase in ["PHASE1", "PHASE2", "PHASE3", "PHASE4", "Unknown"]
    }
    missing_results = session.query(ClinicalTrial).filter_by(status="Unknown").count()
    session.close()
    return {"total": total, "by_phase": by_phase, "missing_results": missing_results}