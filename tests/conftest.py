import os
import pytest
from dotenv import load_dotenv

load_dotenv()


def pytest_configure(config):
    config.addinivalue_line("markers", "readonly: safe read-only endpoints")
    config.addinivalue_line("markers", "destructive: endpoints that mutate state — skip by default")


@pytest.fixture(scope="session")
def base_url():
    url = os.getenv("GRAYLAYER_BASE_URL", "http://gateway.graylayer.tech/api/v1")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def auth_headers():
    key = os.getenv("GRAYLAYER_API_KEY")
    if key:
        return {"X-API-Key": key}
    return {}
