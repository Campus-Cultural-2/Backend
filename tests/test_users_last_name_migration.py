from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from api.app import create_app
from database.config.settings import settings
from tests.test_user_controller import admin_auth_headers

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_deactivate_user_created_before_last_name_was_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Usuarios cadastrados antes da coluna last_name existir ficaram com NULL.
    # Inativar um deles salvava a mudanca, mas a resposta quebrava com 500.
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    command.upgrade(alembic_config, "d4e5f6a7b8c9")
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO users (role, password_hash, email, name, last_name, is_active) "
            "VALUES ('professor', 'unused', 'legacy@example.com', 'Legado', NULL, 1)"
        )
    command.upgrade(alembic_config, "head")

    with sqlite3.connect(db_path) as connection:
        legacy_id = connection.execute(
            "SELECT id FROM users WHERE email = 'legacy@example.com'"
        ).fetchone()[0]

    app = create_app(database_url=f"sqlite:///{db_path}")
    with TestClient(app) as client:
        headers = admin_auth_headers(client)
        deactivated = client.patch(
            f"/users/{legacy_id}/status", headers=headers, json={"is_active": False}
        )
        listed = client.get("/users", headers=headers)

    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert deactivated.json()["last_name"] == ""
    assert listed.status_code == 200
