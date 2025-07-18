from sqlalchemy import Column, String, Date, TIMESTAMP, text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ClinicalTrial(Base):
    """
    Represents a clinical trial in the database.
    """
    __tablename__ = "clinical_trials"
    trial_id = Column(String, primary_key=True)
    title = Column(String)
    phase = Column(String)
    status = Column(String)
    locations = Column(String)
    registered_date = Column(Date)
    snapshot_ts = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    