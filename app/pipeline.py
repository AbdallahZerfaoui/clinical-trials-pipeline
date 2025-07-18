import requests
import logging
import json
from math import log
from datetime import date, timedelta
import datetime as dt
from .models import ClinicalTrial, Base
from .db import engine
from .config import Config
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pipeline:
    """
    Pipeline class to handle the ingestion of clinical trial data.
    It fetches data from an API, normalizes it, and stores it in a database.
    """

    def __init__(self):
        self.initialize_db()
        Session = sessionmaker(bind=engine)
        self.session = Session()
        self.config = Config("config.yaml")

    @staticmethod
    def initialize_db():
        Base.metadata.create_all(bind=engine)
        logger.info("[initialize] Database initialized.")

    def fetch_trials(self, condition: str = "cardiology", days: int = 7):
        starting_date = (date.today() - timedelta(days=days)).isoformat()
        logger.info(f"starting_date : {starting_date}")
        url = f"{self.config.get('api', 'base_url')}{self.config.get('api', 'endpoints', 'studies')}"
        resp = requests.get(
            url,
            timeout=10,
            params={
                "pageSize": self.config.get("api", "request", "page_size"),
                "query.term": f"AREA[LastUpdatePostDate]RANGE[{starting_date},MAX]",
                "query.cond": condition,
                # "filter.overallStatus": "RECRUITING",
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

    def _extract_phase(self, record):
        """Extract phase information from the record."""
        design_module = record["protocolSection"].get("designModule", {})
        phases = design_module.get("phases", [])
        return phases[0] if phases else "Unknown"

    def _extract_locations(self, record):
        """Extract and format location information from the record."""
        contact_location_module = record["protocolSection"].get(
            "contactsLocationsModule", {}
        )
        locations_list = contact_location_module.get("locations", [])

        if len(locations_list) > 1:
            # Use set to remove duplicates, then join
            countries = set(loc.get("country", "Unknown") for loc in locations_list)
            return ";".join(countries)
        elif locations_list:
            return locations_list[0].get("country", "Unknown")
        else:
            return "Global"

    def _extract_num_subjects(self, record):
        """
        Extract the number of subjects from the record.
        """
        try:
            # Check if resultsSection exists at all
            results_section = record.get("resultsSection")
            if not results_section:
                return 0

            # Safely navigate to the list of periods using .get()
            participant_flow = results_section.get("participantFlowModule")
            if not participant_flow:
                return 0

            periods = participant_flow.get("periods", [])
            if not periods:
                return 0

            for period in periods:
                milestones = period.get("milestones", [])

                for milestone in milestones:
                    if milestone.get("type") == "STARTED":
                        # Get the list of achievements, default to empty list
                        achievements = milestone.get("achievements", [])
                        if achievements:
                            # Extract valid numbers only
                            valid_numbers = []
                            for i, achievement in enumerate(achievements):
                                num_subjects_str = achievement.get("numSubjects")
                                if num_subjects_str is not None:
                                    try:
                                        num = int(num_subjects_str)
                                        valid_numbers.append(num)
                                    except (ValueError, TypeError):
                                        logger.error(
                                            f"Could not convert '{num_subjects_str}' to int"
                                        )

                            if valid_numbers:
                                total = sum(valid_numbers)
                                return total
                            else:
                                logger.warning("No valid numbers found in achievements")
                        else:
                            logger.warning(
                                "No achievements found for STARTED milestone"
                            )

        except Exception as e:
            logger.error(f"Error extracting num_subjects: {e}")
            return 0

        logger.info("No STARTED milestone found or no valid data")
        return 0

    def _extract_basic_info(self, record):
        """Extract basic trial information."""
        protocol_section = record["protocolSection"]
        identification = protocol_section["identificationModule"]
        status_module = protocol_section["statusModule"]

        return {
            "trial_id": identification["nctId"],
            "title": identification["briefTitle"],
            "status": status_module["overallStatus"] or "Unknown",
            "registered_date": dt.datetime.fromisoformat(
                status_module["studyFirstSubmitDate"]
            ),
            "last_update_date": dt.datetime.fromisoformat(
                status_module["lastUpdatePostDateStruct"]["date"]
            ),
            "snapshot_ts": dt.datetime.now(),
        }

    def normalize(self, record):
        """Normalize a clinical trial record into a ClinicalTrial object."""
        basic_info = self._extract_basic_info(record)
        phase = self._extract_phase(record)
        locations = self._extract_locations(record)
        num_subjects = self._extract_num_subjects(record)

        trial = ClinicalTrial(
            phase=phase, locations=locations, num_subjects=num_subjects, **basic_info
        )

        return trial

    def _calculate_urgency_score(self, trial):
        """
        Calculate urgency score based on trial's last update date.
        More recent updates yield higher scores.
        the more subjects, the higher the score.
        """
        days_since_update = (dt.datetime.now() - trial.last_update_date).days
        urgency_score = log(1 + trial.num_subjects) / (days_since_update + 1)
        return round(urgency_score, 2)

    def run_ingestion(self, condition: str = "cardiology", days: int = 7):
        """
        Run the ingestion pipeline to fetch, normalize, and store clinical trials.
        """
        trials = self.fetch_trials(condition=condition, days=days)
        for rec in trials:
            trial = self.normalize(rec)
            trial.urgency_score = self._calculate_urgency_score(trial)
            self.session.merge(trial)
        self.session.commit()
        self.session.close()
