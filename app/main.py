from .pipeline import Pipeline


def main():
    pipeline = Pipeline()
    pipeline.run_ingestion()

if __name__ == "__main__":
    main()
