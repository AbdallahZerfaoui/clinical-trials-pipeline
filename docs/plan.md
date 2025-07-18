# clinical-trials-pipeline


## Day 1 – Foundation & Ingestion

### 1. Morning (2–3 h): Project scaffold & infra stub

1. **Create repo**

   * Initialize Git, `main` branch, add MIT or Apache license.
   * Commit a basic `README.md` with project goal and “Status: 🚧 In progress.”
2. **Set up virtual env & deps**

   * `python3 -m venv .venv && source .venv/bin/activate`
   * `pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic requests boto3 alembic`
   * Freeze into `requirements.txt`.
3. **Terraform stub** (`terraform/` folder)

   * `provider "aws" { region = var.aws_region }`
   * Empty for now: buckets, RDS, Lambda placeholders.
   * `variables.tf` with `aws_region`, `db_name`, `db_user`, `db_pass`, `s3_bucket`.
   * Commit and push.

### 2. Late morning (1–2 h): Database schema & ORM models

1. **Define schema**

   ```sql
   CREATE TABLE clinical_trials (
     trial_id TEXT PRIMARY KEY,
     title TEXT,
     phase TEXT,
     status TEXT,
     locations TEXT,
     registered_date DATE,
     snapshot_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```
2. **`app/models.py`**

   ```python
   from sqlalchemy import Column, String, Date, TIMESTAMP, text
   from sqlalchemy.ext.declarative import declarative_base

   Base = declarative_base()

   class ClinicalTrial(Base):
       __tablename__ = "clinical_trials"
       trial_id = Column(String, primary_key=True)
       title = Column(String)
       phase = Column(String)
       status = Column(String)
       locations = Column(String)
       registered_date = Column(Date)
       snapshot_ts = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
   ```
3. **`app/db.py`**

   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker

   DATABASE_URL = "postgresql://<user>:<pass>@<host>:5432/<db>"
   engine = create_engine(DATABASE_URL)
   SessionLocal = sessionmaker(bind=engine)
   ```
4. Commit and push.

### 3. Afternoon (2–3 h): Ingestion pipeline

1. **`app/pipeline.py`**

   ```python
   import requests
   from datetime import date, timedelta
   from app.models import ClinicalTrial, Base
   from app.db import engine, SessionLocal

   Base.metadata.create_all(bind=engine)

   def fetch_trials(condition: str = "oncology"):
       last_week = (date.today() - timedelta(days=7)).isoformat()
       url = (
         "https://clinicaltrials.gov/api/query/study_fields"
         f"?expr={condition}&fields=NCTId,BriefTitle,Phase,OverallStatus,LocationCountry,StudyFirstSubmitDate"
         f"&min_rnk=1&max_rnk=100&fmt=json"
         f"&min_rnk=1&max_rnk=100&study_first_submit_date={last_week}"
       )
       resp = requests.get(url)
       data = resp.json()["StudyFieldsResponse"]["StudyFields"]
       return data

   def normalize(record):
       return ClinicalTrial(
           trial_id=record["NCTId"][0],
           title=record["BriefTitle"][0],
           phase=record["Phase"][0] or "Unknown",
           status=record["OverallStatus"][0] or "Unknown",
           locations=";".join(record["LocationCountry"]) or "Global",
           registered_date=record["StudyFirstSubmitDate"][0]
       )

   def run_ingestion():
       session = SessionLocal()
       trials = fetch_trials()
       for rec in trials:
           trial = normalize(rec)
           session.merge(trial)
       session.commit()
       session.close()
   ```
2. **Smoke test**

   * Launch REPL: `python -c "from app.pipeline import run_ingestion; run_ingestion()"`
   * Connect to local Postgres and verify rows in `clinical_trials`.
3. Commit and push.

### 4. Late afternoon (1 h): Basic export to S3 (optional)

1. Add to `app/pipeline.py` after DB write:

   ```python
   import json, boto3
   s3 = boto3.client("s3")
   def export_snapshot(bucket: str):
       session = SessionLocal()
       rows = session.query(ClinicalTrial).all()
       payload = [r.__dict__ for r in rows]
       s3.put_object(
         Bucket=bucket,
         Key=f"snapshots/{date.today().isoformat()}.json",
         Body=json.dumps(payload, default=str),
         ContentType="application/json"
       )
   ```
2. Test locally (requires valid AWS creds in env).
3. Commit and push.

---

## Day 2 – API, Docs & Polish

### 1. Morning (2 h): FastAPI service

1. **`app/main.py`**

   ```python
   from fastapi import FastAPI, HTTPException
   from app.db import SessionLocal
   from app.models import ClinicalTrial
   from app.pipeline import run_ingestion, export_snapshot

   app = FastAPI(title="ClinicalTrials.gov PoC")

   @app.on_event("startup")
   def startup_event():
       # optionally run ingestion on start
       pass

   @app.post("/run")
   def trigger_run():
       try:
           run_ingestion()
           return {"status": "ingested"}
       except Exception as e:
           raise HTTPException(status_code=500, detail=str(e))

   @app.get("/summary")
   def get_summary():
       session = SessionLocal()
       total = session.query(ClinicalTrial).count()
       by_phase = {
           phase: session.query(ClinicalTrial).filter_by(phase=phase).count()
           for phase in ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Unknown"]
       }
       missing_results = session.query(ClinicalTrial).filter_by(status="Unknown").count()
       session.close()
       return {"total": total, "by_phase": by_phase, "missing_results": missing_results}
   ```
2. **Run locally**:

   ```bash
   uvicorn app.main:app --reload --port 8000
   curl http://localhost:8000/run
   curl http://localhost:8000/summary
   ```
3. Commit and push.

### 2. Late morning (1 h): Terraform → AWS deploy stub

1. In `terraform/`, flesh out modules:

   * RDS instance (db.t3.micro), credentials from SSM or env.
   * S3 bucket with versioning off.
   * Lambda function using a prebuilt Docker image (from `Dockerfile`) or zip pointing at `app.main:app`.
   * API Gateway HTTP API with two routes (`POST /run`, `GET /summary`) pointing to Lambda.
   * IAM role granting Lambda RDS Data API or direct network access, and S3 PutObject.
2. Do `terraform init` and `plan` to prove the infra deploys (no need to apply if cost is a concern).
3. Commit and push.

### 3. Afternoon (2 h): Documentation & tech brief

1. **README.md** update:

   * Project overview & problem statement.
   * Setup instructions (venv, database, AWS creds).
   * Local run steps.
   * AWS deploy steps (Terraform apply).
   * API docs: list endpoints & sample responses.
   * Next steps: add monitoring, handle pagination, LLM summarizer placeholder.
2. **One‑page tech brief** (`docs/brief.md` or PDF):

   * Architecture diagram (ASCII art or embedded small PlantUML): data flow from ClinicalTrials.gov → Lambda → RDS → S3 → FastAPI.
   * How this maps to the global health research use case.
3. Commit and push.

### 4. Late afternoon (1 h): Final sanity check & delivery email draft

1. **Run full end‑to‑end**:

   * `curl /run` → ingest fresh data.
   * `curl /summary` → verify correct counts.
   * Check S3 bucket for JSON snapshot.
2. **Proofread README & brief**, fix typos.
3. **Draft update email** (use template from earlier), insert repo URL.
4. Push one final commit, tag `v1.0‑poC`.

---

**By end of Day 2**, you’ll have:

* A public GitHub repo with code, infra, docs.
* A working FastAPI service hitting RDS & S3.
* Terraform files proving deploy readiness.
* A one‑page brief mapping to the role.
* Update email ready to send.

This plan balances speed with enough substance to impress and make the shortlist. Good luck!
