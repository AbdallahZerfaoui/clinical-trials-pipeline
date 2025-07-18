import os
from fastapi import Header, HTTPException, status
from dotenv import load_dotenv

load_dotenv()
VALID_KEYS = set(os.getenv("API_KEYS", "").split(","))

def api_key_guard(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    API key guard to protect endpoints.
    Validates the API key against a set of predefined keys.
    """
    if x_api_key not in VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return x_api_key
