"""Login, logout and the lockout (DECISIONS #47, #48)."""

from typing import Any

import pytest
from django.contrib.auth.models import User
from django.test import Client, RequestFactory, override_settings

from accounts.client_ip import client_ip

pytestmark = pytest.mark.django_db

PASSWORD = "synthetic-pass"


@pytest.fixture
def owner() -> User:
    return User.objects.create_user("owner", password=PASSWORD)


def log_in(c: Client, password: str, username: str = "owner", next: str = "/") -> Any:
    return c.post("/login/", {"username": username, "password": password, "next": next})


def logged_in(c: Client) -> bool:
    return c.get("/api/me").status_code == 200


def test_login_page_renders() -> None:
    response = Client().get("/login/?next=/inbox/")
    assert response.status_code == 200
    assert b'name="password"' in response.content
    assert b'value="/inbox/"' in response.content


def test_login_goes_to_next(owner: User) -> None:
    c = Client()
    response = log_in(c, PASSWORD, next="/inbox/")
    assert response.status_code == 302
    assert response["Location"] == "/inbox/"
    assert logged_in(c)


def test_login_never_redirects_off_site(owner: User) -> None:
    response = log_in(Client(), PASSWORD, next="https://elsewhere.example/")
    assert response["Location"] == "/"


def test_wrong_password_shows_the_form_again(owner: User) -> None:
    c = Client()
    response = log_in(c, "wrong")
    assert response.status_code == 200
    assert b'role="alert"' in response.content
    assert not logged_in(c)


def test_five_failures_lock_even_the_right_password(owner: User) -> None:
    c = Client()
    for _ in range(5):
        log_in(c, "wrong")
    response = log_in(c, PASSWORD)
    assert response.status_code == 429
    assert b"paused for 15 minutes" in response.content
    assert not logged_in(c)


def test_lock_is_per_ip_and_username(owner: User) -> None:
    attacker = Client(REMOTE_ADDR="203.0.113.7")
    for _ in range(5):
        log_in(attacker, "wrong")
    assert log_in(attacker, PASSWORD).status_code == 429

    # Someone else's failures don't lock the owner out from their own address.
    me = Client(REMOTE_ADDR="198.51.100.2")
    log_in(me, PASSWORD)
    assert logged_in(me)


def test_success_resets_the_count(owner: User) -> None:
    c = Client()
    for _ in range(4):
        log_in(c, "wrong")
    log_in(c, PASSWORD)
    c.post("/logout/")
    for _ in range(4):
        log_in(c, "wrong")
    log_in(c, PASSWORD)
    assert logged_in(c)


def test_admin_login_counts_too(owner: User) -> None:
    c = Client()
    for _ in range(5):
        c.post("/admin/login/", {"username": "owner", "password": "wrong"})
    assert log_in(c, PASSWORD).status_code == 429


@override_settings(CLIENT_IP_HEADER="CF-Connecting-IP")
def test_behind_a_tunnel_each_real_ip_is_its_own_lock(owner: User) -> None:
    # Every request comes from the tunnel on 127.0.0.1; only the header differs.
    attacker = Client(REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.7")
    for _ in range(5):
        log_in(attacker, "wrong")
    assert log_in(attacker, PASSWORD).status_code == 429

    me = Client(REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.2")
    log_in(me, PASSWORD)
    assert logged_in(me)


def test_client_ip_reads_the_configured_header() -> None:
    rf = RequestFactory()
    plain = rf.get("/", REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.7")
    assert client_ip(plain) == "127.0.0.1"  # no header configured: the connection

    with override_settings(CLIENT_IP_HEADER="CF-Connecting-IP"):
        assert client_ip(plain) == "203.0.113.7"
        assert client_ip(rf.get("/", REMOTE_ADDR="127.0.0.1")) == "127.0.0.1"  # header missing

    with override_settings(CLIENT_IP_HEADER="X-Forwarded-For"):
        # The client can put anything first; the last entry is what our proxy saw.
        chain = rf.get("/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="10.0.0.1, 203.0.113.7")
        assert client_ip(chain) == "203.0.113.7"


def test_logout_is_post_only(owner: User) -> None:
    c = Client()
    c.force_login(owner)
    assert c.get("/logout/").status_code == 405
    response = c.post("/logout/")
    assert response["Location"] == "/login/"
    assert not logged_in(c)
