import requests
from datetime import date, timedelta
from app.models import ClinicalTrial, Base
from app.db import engine
from sqlalchemy.orm import sessionmaker
import logging
import json
import datetime as dt

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
        url = "https://clinicaltrials.gov/api/v2/studies"
        resp = requests.get(
            url,
            timeout=10,
            params={
                "pageSize": 1000,
                "query.term": "AREA[LastUpdatePostDate]RANGE[2025-07-17,MAX]",
            },
        )
        logger.info(f"status code: {resp.status_code}")
        data = resp.json()["studies"]
        if data:
            json_data = json.dumps(data, indent=2)
            with open("data/clinical_trials.json", "w") as f:
                f.write(json_data)
        logger.info(f"Fetched {len(data)} trials.")
        return data

    def normalize(self, record):
        # Safely get phases - it might not exist
        design_module = record["protocolSection"].get("designModule", {})
        phases = design_module.get("phases", [])
        phase = phases[0] if phases else "Unknown"
        # Safely get locations_list
        contact_location_module = record["protocolSection"].get(
            "contactsLocationsModule", {}
        )
        locations_list = contact_location_module.get("locations", [])

        trial = ClinicalTrial(
            trial_id=record["protocolSection"]["identificationModule"]["nctId"],
            title=record["protocolSection"]["identificationModule"]["briefTitle"],
            phase=phase,
            status=record["protocolSection"]["statusModule"]["overallStatus"]
            or "Unknown",
            registered_date=dt.datetime.fromisoformat(
                record["protocolSection"]["statusModule"]["studyFirstSubmitDate"]
            ),
            snapshot_ts=dt.datetime.now(),
        )
        # locations_list=record["protocolSection"]["contactsLocationsModule"]["locations"]
        if len(locations_list) > 1:
            trial["locations"] = ";".join(
                set(locations_list[i]["country"] for i in range(len(locations_list)))
            )
        elif locations_list:
            trial["locations"] = locations_list[0]["country"]
        else:
            trial["locations"] = "Global"

        return trial

    def run_ingestion(self):
        trials = self.fetch_trials()
        for rec in trials:
            trial = self.normalize(rec)
            self.session.merge(trial)
        self.session.commit()
        self.session.close()
