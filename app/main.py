from fastapi import FastAPI, HTTPException, Depends, Request
# from .db import SessionLocal
from app.models import ClinicalTrial
from .dependencies import get_pipeline, Pipeline
from .security import api_key_guard
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="ClinicalTrials.gov PoC")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

welcome_message = "As a demo of exactly the kind of automation I’d build, \
I’ve created an Active Oncology Trial Alerts endpoint. \
In one weekend I’ll show you an API that pulls only Phase II/III recruiting trials \
updated in the last 7 days in Europe, computes a simple urgency score, and exposes \
it via /trials/active‑oncology. \
It’s live at [PoC URL] and the full Terraform + Python code is at [GitHub link]."


@app.get("/", dependencies=[Depends(api_key_guard)])
@limiter.limit("10/minute")
def read_root(request: Request):
    """
    Root endpoint that returns a welcome message.
    """
    return {"message": welcome_message}


@app.get("/health")
def health_check():
    """
    Health check endpoint to verify the service is running.
    """
    return {"status": "ok"}


@app.get("/ping_db")
def ping_db(pipeline: Pipeline = Depends(get_pipeline)):
    """
    Ping the database to check connectivity.
    """
    try:
        # Simple query to check if database is accessible
        count = pipeline.session.query(ClinicalTrial).count()
        return {
            "status": "ok",
            "message": "Database connection successful",
            "total_trials": count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database connection failed: {str(e)}"
        )


@app.post("/run")
def trigger_run(
    condition: str = "cardiology",
    days: int = 7,
    pipeline: Pipeline = Depends(get_pipeline),
):
    try:
        pipeline.run_ingestion(condition=condition, days=days)
        return {"status": "ingested"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/summary")
def get_summary(pipeline: Pipeline = Depends(get_pipeline)):
    session = pipeline.session
    total = session.query(ClinicalTrial).count()
    by_phase = {
        phase: session.query(ClinicalTrial).filter_by(phase=phase).count()
        for phase in ["PHASE1", "PHASE2", "PHASE3", "PHASE4", "Unknown"]
    }
    missing_results = session.query(ClinicalTrial).filter_by(status="Unknown").count()
    session.close()
    return {"total": total, "by_phase": by_phase, "missing_results": missing_results}


@app.get(
    "/urgent",
    description="Get urgent clinical trials --  0-all 1-urgent 3-highly-urgent 5-extremely-urgent",
)
def get_urgent_trials(level: int = 0, pipeline: Pipeline = Depends(get_pipeline)):
    session = pipeline.session
    urgent_trials = (
        session.query(ClinicalTrial)
        .filter(ClinicalTrial.urgency_score > level)
        .order_by(ClinicalTrial.urgency_score.desc())
        .all()
    )
    session.close()
    return {"urgent_trials": urgent_trials}
