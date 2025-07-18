import requests
import logging
import json
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

    def fetch_trials(self, condition: str = "cardiology", days: int = 3):
        starting_date = (date.today() - timedelta(days=days)).isoformat()
        print(f"starting_date : {starting_date}")
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
                # print("No resultsSection found")
                return 0
            
            # Safely navigate to the list of periods using .get()
            participant_flow = results_section.get("participantFlowModule")
            if not participant_flow:
                # print("No participantFlowModule found")
                return 0
            
            periods = participant_flow.get("periods", [])
            if not periods:
                # print("No periods found")
                return 0
            
            # print(f"Found {len(periods)} periods")
            
            for period_idx, period in enumerate(periods):
                # print(f"Processing period {period_idx}")
                milestones = period.get("milestones", [])
                
                for milestone_idx, milestone in enumerate(milestones):
                    # print(f"  Processing milestone {milestone_idx}, type: {milestone.get('type')}")
                    
                    if milestone.get("type") == "STARTED":
                        # Get the list of achievements, default to empty list
                        achievements = milestone.get("achievements", [])
                        if achievements:
                            # print(f"    Found {len(achievements)} achievements")
                            # Extract valid numbers only
                            valid_numbers = []
                            for i, achievement in enumerate(achievements):
                                num_subjects_str = achievement.get("numSubjects")
                                # print(f"      Achievement {i}: numSubjects = {num_subjects_str}")
                                
                                if num_subjects_str is not None:
                                    try:
                                        num = int(num_subjects_str)
                                        valid_numbers.append(num)
                                    except (ValueError, TypeError):
                                        print(f"        Could not convert '{num_subjects_str}' to int")
                            
                            if valid_numbers:
                                total = sum(valid_numbers)
                                # print(f"    Total subjects: {total}")
                                return total
                            else:
                                print("    No valid numbers found in achievements")
                        else:
                            print("    No achievements found for STARTED milestone")
                            
        except Exception as e:
            print(f"Error extracting num_subjects: {e}")
            return 0

        print("No STARTED milestone found or no valid data")
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
            phase=phase,
            locations=locations,
            num_subjects=num_subjects,
            **basic_info
        )

        return trial

    def run_ingestion(self):
        trials = self.fetch_trials()
        for rec in trials:
            trial = self.normalize(rec)
            self.session.merge(trial)
        self.session.commit()
        self.session.close()
