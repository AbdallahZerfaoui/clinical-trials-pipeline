import yaml
from pathlib import Path


class Config:
    """
    Simple configuration loader for YAML files.
    Usage:
    config = Config("config.yaml")
    value = config.get('section', 'subsection', 'key', default='default_value')
    """
    def __init__(self, path: str = "config.yaml"):
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"Config file not found: {self._path}")
        with self._path.open() as f:
            self._data = yaml.safe_load(f)

    def get(self, *keys, default=None):
        """
        Navigate nested dicts via get('section', 'subsection', 'key').
        Returns default if any key is missing.
        """
        d = self._data
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return default
            d = d[key]
        return d

    def as_dict(self):
        """Return the full config as a dict."""
        return self._data
