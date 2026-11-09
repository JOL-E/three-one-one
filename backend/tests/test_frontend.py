"""The built app is served by Django itself (DECISIONS #52)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client, override_settings

SHELL = b"<!doctype html><title>311 test shell</title>"


@pytest.fixture
def built_app(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_bytes(SHELL)
    return tmp_path


@pytest.mark.parametrize("path", ["/inbox/", "/inbox/3F9A", "/p/0b6f/3F9A", "/search/"])
def test_app_screens_get_the_app_shell(built_app: Path, path: str) -> None:
    with override_settings(FRONTEND_DIR=built_app):
        response = Client().get(path)
    assert response.status_code == 200
    assert response.content == SHELL
    assert response["Cache-Control"] == "no-cache"


SERVER_PATHS = ["/api/nope", "/oauth/nope/", "/.well-known/nope", "/static/nope.css", "/mcp/"]


@pytest.mark.django_db
@pytest.mark.parametrize("path", SERVER_PATHS)
def test_server_paths_never_get_the_app_shell(built_app: Path, path: str) -> None:
    with override_settings(FRONTEND_DIR=built_app):
        response = Client().get(path)
    assert response.status_code == 404
    assert response.content != SHELL


def test_unbuilt_app_is_a_404_with_a_hint(tmp_path: Path) -> None:
    with override_settings(FRONTEND_DIR=tmp_path):
        response = Client().get("/inbox/")
    assert response.status_code == 404


def test_production_settings_pass_the_deploy_check(tmp_path: Path) -> None:
    """`check --deploy` with an https BASE_URL: no warnings left (HTTPS settings, cookies, HSTS)."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DEBUG": "0",
        "SECRET_KEY": "synthetic-" + "k3y-Q8z-" * 8,
        "BASE_URL": "https://311.example.com",
        "DATA_DIR": str(tmp_path),
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=Path(__file__).parent.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
