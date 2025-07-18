# app/dependencies.py
from .pipeline import Pipeline

def get_pipeline():
    pipeline = Pipeline()
    try:
        yield pipeline
    finally:
        pipeline.session.close()
