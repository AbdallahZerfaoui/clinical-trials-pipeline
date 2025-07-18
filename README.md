# Clinical Trials PoC – Active Trial Intelligence API

> **Goal:** Show—in a compact, production‑shaped package—how to ingest raw ClinicalTrials.gov data, normalize & enrich it (enrollment + urgency scoring), persist it, and expose focused endpoints with basic security & abuse protection. Exactly the muscles needed for the larger contract project.

---

## 1. Why this PoC Matters

Public trial registries force analysts to sift through verbose, heterogeneous JSON. This PoC turns that into concise, queryable, enriched API resources (e.g. *urgent trials*) while demonstrating engineering maturity: config management, persistence, scoring logic, auth, rate limiting, health checks, and future AI hooks (summaries / criteria extraction).

---

## 2. High‑Level Flow

```
+-----------+    fetch (HTTP)    +------------------+   normalize/enrich   +-------------+
| Upstream  |  ----------------> | Ingestion Logic  |  ------------------> | SQLite / RDS|
| API       |                    | (Pipeline)       |                     | (Clinical   |
| (CT.gov)  |                    +------------------+                     | Trials Table|
+-----------+                            |                                 +-------------+
                                          v                                        ^
                                    Urgency score calc                            |
                                          |                                       read
                                          v                                        |
                                      FastAPI Service <---- clients (curl, web, internal tools)
                                         (secured & rate‑limited)
```

---

## 3. Key Design Choices

| Decision                                 | Rationale                                                                       |
| ---------------------------------------- | ------------------------------------------------------------------------------- |
| **FastAPI** service layer                | Async‑friendly, automatic OpenAPI docs, easy dependency injection.              |
| **Dependency injector (`get_pipeline`)** | Fresh DB session per request, deterministic cleanup (no leaked connections).    |
| **SQLite (local) via SQLAlchemy**        | Zero setup for PoC; swap to Postgres/RDS later without model rewrite.           |
| **Explicit `ClinicalTrial` ORM model**   | Declarative schema; enables indexing/migrations; clear contract for enrichment. |
| **Config loader class**                  | Centralizes YAML access; avoids magic literals spread through code.             |
| **Urgency score uses log(enrollment)**   | Log dampens outliers; recency in denominator surfaces *recent + large* trials.  |
| **API key + rate limiting**              | Simple abuse protection; demonstrates security layering.                        |
| **Health endpoints**                     | Support liveness/readiness probes & quick smoke tests.                          |
| **Single ingestion trigger `/run`**      | Manual refresh during PoC; can evolve to scheduled/event‑driven ingestion.      |

---

## 4. Data Model (ClinicalTrial)

Fields: `trial_id, title, phase, status, locations, registered_date, last_update_date, num_subjects, urgency_score, snapshot_ts`.

### Enrollment Extraction

`num_subjects` = sum of `STARTED` milestone achievements across all groups. Robust defensive parsing (nested `.get()` with defaults) so incomplete records safely fall back to 0.

### Urgency Score

Formula (PoC version):

```
urgency_score = log(1 + num_subjects) / (days_since_update + 1)
```

*Why*: log smooths large enrollment targets; `+1` prevents division by zero; denominator favors recent updates. Rounded to 2 decimals for compact API responses.

> **If your code currently uses the simpler `E/(D+1)` form, update either the code or this README for consistency.**

---

## 5. API Surface (Current)

| Endpoint   | Method | Auth      | Rate Limited | Purpose                                         |
| ---------- | ------ | --------- | ------------ | ----------------------------------------------- |
| `/`        | GET    | API key   | Yes          | Welcome/info (demo narrative).                  |
| `/health`  | GET    | No        | No           | Liveness probe.                                 |
| `/ping_db` | GET    | No        | No           | DB connectivity + row count.                    |
| `/run`     | POST   | No        | No           | Manual ingestion trigger (`condition`, `days`). |
| `/summary` | GET    | No        | No           | Aggregate counts by phase; basic stats.         |
| `/urgent`  | GET    | (Planned) | (Planned)    | Trials sorted by urgency threshold `level`.     |

> **Hardening To‑Do:** Apply API key + rate limits consistently to data endpoints (currently shown only on `/`).

---

## 6. Ingestion & Normalization Pipeline

1. **Fetch**: Build date window (`days` back), query API with page size from config, archive raw JSON (auditability).
2. **Extract**: Dedicated helpers (`_extract_phase`, `_extract_locations`, `_extract_num_subjects`) isolate brittle JSON traversal.
3. **Normalize**: Create / merge `ClinicalTrial` instances (idempotent upsert).
4. **Enrich**: Calculate urgency score (future: LLM summary, keyword extraction).
5. **Persist**: Batch commit for efficiency; session closed via dependency cleanup.

---

## 7. Security & Abuse Protection

* **API Key Header**: `X-API-Key` validated against env var (`API_KEYS`).
* **Rate Limiting**: `slowapi` decorator (e.g. `@limiter.limit("10/minute")`).
* **Next**: Per‑key quotas, structured audit logging, optional JWT / OAuth if integrating with identity provider.

---

## 8. Configuration Strategy

Custom `Config` wrapper abstracts nested YAML access (`config.get("api", "request", "page_size")`). Shields code from `KeyError` and centralizes defaults. Migration path: Pydantic `BaseSettings` + environment variable precedence.

---

## 9. Local Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export API_KEYS="devkey123"
uvicorn app.main:app --reload
# Trigger ingestion
curl -X POST "http://localhost:8000/run?condition=oncology&days=7"
# View urgent trials
curl "http://localhost:8000/urgent?level=1"
```

---

## 10. Deployment Notes

* **SQLite** retained for footprint; switch to Postgres (RDS) for multi‑user concurrency (avoid writer locks).
* **Process Model**: `uvicorn main:app` (PoC). Production: Gunicorn + multiple Uvicorn workers or container orchestrator.
* **Containerization** (Next): Add `Dockerfile`; build & push through CI/CD (GitHub Actions → registry → Terraform).
* **Terraform**: Existing script provisions VM + systemd service; can evolve to module‑based infra.

---

## 11. What Could Be Next (Impact‑Focused Roadmap)

| Stage | Enhancement                               | Value                                        | Effort |
| ----- | ----------------------------------------- | -------------------------------------------- | ------ |
| 1     | **LLM Summaries (Ollama)**                | Human digest per trial; analyst time saved.  | Low    |
| 1     | **Eligibility Keyword Extraction**        | Filter by mechanism (PD‑1, CAR‑T).           | Low    |
| 2     | **Delta Tracking Table**                  | Detect status/enrollment changes.            | Med    |
| 2     | **Caching Layer (Redis)**                 | Lower latency; rate‑limit resilience.        | Med    |
| 2     | **Auth Hardening (JWT / per‑key limits)** | Enterprise readiness.                        | Med    |
| 3     | **Async Fetch + Backoff**                 | Higher throughput, resilience to throttling. | Med    |
| 3     | **Observability (Prometheus / OTEL)**     | SLA & performance insight.                   | Med    |
| 3     | **Multi‑tenant Partitioning**             | Serve segregated partner views.              | High   |
| 4     | **Enrollment Velocity ML**                | Predict completion timelines.                | High   |

---

## 12. Trade‑offs & Current Limitations

| Area           | Current State       | Trade‑off                 | Mitigation                          |
| -------------- | ------------------- | ------------------------- | ----------------------------------- |
| DB Backend     | SQLite file         | Limited concurrent writes | Migrate to Postgres + Alembic       |
| Error Handling | Basic try/except    | Sparse error taxonomy     | Custom exceptions + global handlers |
| Auth Coverage  | Partial             | Inconsistent protection   | Apply key dependency globally       |
| Rate Limiting  | Only root example   | Other endpoints open      | Decorate all public routes          |
| Ingestion      | Sync, single thread | Slower for large batches  | Async + pagination + batching       |
| Logging        | Basic INFO          | Harder correlation        | Structured JSON + request IDs       |
| Migrations     | None                | Schema evolution friction | Introduce Alembic early             |

---

## 13. Extensibility Hooks

* **`Pipeline.normalize()`**: Insert AI summaries, keyword extraction pre‑merge.
* **`_calculate_urgency_score`**: Swap in weighted or normalized formula (e.g. recency weight).
* **Security layer**: Replace static key set with datastore (Redis) mapping key → quota.

---

## 14. Quick Demo Script

1. `GET /health` (service up).
2. `POST /run?condition=oncology&days=7` (ingestion).
3. `GET /summary` (aggregates).
4. `GET /urgent?level=1` (ranked urgency list).
5. (Future) Show `summary` field once LLM enrichment added.

---

## 15. Contributor Onboarding (Future)

Add `CONTRIBUTING.md`: style guide, how to add a new extractor, test conventions, security review checklist, performance regression protocol.

---

## 16. License

Use a permissive license (MIT / Apache‑2.0) unless organizational policy dictates otherwise.

---

**TL;DR:** This PoC already demonstrates ingestion, normalization, enrichment, persistence, API exposure, and baseline security controls. The roadmap elevates it into a differentiated *trial intelligence service* with minimal incremental complexity.
