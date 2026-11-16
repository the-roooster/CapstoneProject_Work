from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1 import auth
from app.rate_limit import LoginRateLimiter


def test_login_limits_failures_by_ip_and_email(monkeypatch):
    monkeypatch.setattr(auth, "login_rate_limiter", LoginRateLimiter())
    monkeypatch.setattr(auth, "verify_password", lambda password, _: password == "correct")
    monkeypatch.setattr(auth, "create_access_token", lambda email: "test-token")
    db = SimpleNamespace(scalar=lambda statement: SimpleNamespace(email="analyst@example.com", password_hash="hash"))
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [],
                       "client": ("192.0.2.1", 1234), "server": ("test", 80), "scheme": "http"})
    form = SimpleNamespace(username=" Analyst@Example.com ", password="wrong")
    for _ in range(5):
        with pytest.raises(HTTPException) as error:
            auth.login(request, form, db)
        assert error.value.status_code == 401
    with pytest.raises(HTTPException) as error:
        auth.login(request, form, db)
    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "60"
    other = SimpleNamespace(username="different@example.com", password="correct")
    assert auth.login(request, other, db)["access_token"] == "test-token"
