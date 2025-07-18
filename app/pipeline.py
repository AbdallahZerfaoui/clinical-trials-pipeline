import requests
from datetime import date, timedelta
from app.models import ClinicalTrial, Base
from app.db import engine
from sqlalchemy.orm import sessionmaker
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self):
        self.initialize_db()
        Session = sessionmaker(bind=engine)
        self.session = Session()

    @staticmethod
    def initialize_db():
        Base.metadata.create_all(bind=engine)
        logger.info("[initialize] Database initialized.")

    def fetch_trials(self, condition: str = "oncology"):
        last_week = (date.today() - timedelta(days=7)).isoformat()
        url = ("https://clinicaltrials.gov/api/v2/studies")
        resp = requests.get(url, timeout=10, params={
            "pageSize": 1000,
            "query.term": "AREA[LastUpdatePostDate]RANGE[2025-07-17,MAX]",
            })
        logger.info(f"status code: {resp.status_code}")
        data = resp.json()["studies"]
        if data:
            json_data = json.dumps(data, indent=2)
            with open("data/clinical_trials.json", "w") as f:
                f.write(json_data)
        logger.info(f"Fetched {len(data)} trials.")
        return data

    def normalize(self, record):
        return ClinicalTrial(
            trial_id=record["protocolSection"]["identificationModule"]["nctId"],
            title=record["protocolSection"]["identificationModule"]["briefTitle"],
            phase=record["protocolSection"]["designModule"]["phases"][0] or "Unknown",
            status=record["protocolSection"]["statusModule"]["overallStatus"][0] or "Unknown",
            locations=";".join(record["protocolSection"]["contactsLocationsModule"]["locations"]["country"]) or "Global",
            registered_date=record["protocolSection"]["statusModule"]["StudyFirstSubmitDate"][0]
        )

    def run_ingestion(self):
        trials = self.fetch_trials()
        for rec in trials:
            trial = self.normalize(rec)
            self.session.merge(trial)
        self.session.commit()
        self.session.close()
