from sqlalchemy import create_engine
from pathlib import Path


db_path = Path(__file__).parent.parent / "data/clinical_trials.db"
if not db_path.exists():
    db_path.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{db_path}"
engine = create_engine(DATABASE_URL)
