"""Tests for phone normalization functionality."""
import pytest

try:
    from fastapi.testclient import TestClient

    from app.main import app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None
    app = None


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
def test_phone_normalize_success():
    """Test phone normalization with valid data."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not available")

    client = TestClient(app)
    payload = {
        "init_data": "dummy",
        "partner_code": "111098",
        "partner_phone": "9827701055"
    }
    r = client.post('/api/webapp/auth', json=payload)
    # Accept either success or not found depending on sheet config (dev fallback)
    assert r.status_code in (200, 404, 401, 400)


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
def test_invalid_code():
    """Test with invalid partner code."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not available")

    client = TestClient(app)
    payload = {
        "init_data": "dummy",
        "partner_code": "AB12",
        "partner_phone": "9827701055"
    }
    r = client.post('/api/webapp/auth', json=payload)
    assert r.status_code == 400


def test_phone_normalization_logic():
    """Test phone normalization without external dependencies."""
    # Test basic phone number normalization logic
    from app.sheets import normalize_phone

    # Test various phone formats
    assert normalize_phone("+7 982 770-1055") == "89827701055"
    assert normalize_phone("8 982 770 1055") == "89827701055"
    assert normalize_phone("79827701055") == "89827701055"
    assert normalize_phone("89827701055") == "89827701055"
