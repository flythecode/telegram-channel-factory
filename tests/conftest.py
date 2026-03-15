from collections import defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keep tests deterministic regardless of the developer's local .env.
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["RUNTIME_MODE"] = "stub"
os.environ["PUBLISHER_BACKEND"] = "stub"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.content_task import ContentTask  # noqa: E402
from app.models.draft import Draft  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.publication import Publication  # noqa: E402
from app.models.telegram_channel import TelegramChannel  # noqa: E402


class FakeQuery:
    def __init__(self, items: list[Any]):
        self._items = list(items)

    def order_by(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._items)


class FakeSession:
    def __init__(self):
        self.storage: dict[type, list[Any]] = defaultdict(list)

    def _apply_model_defaults(self, obj: Any):
        table = getattr(obj.__class__, '__table__', None)
        if table is None:
            return
        for column in table.columns:
            if getattr(obj, column.key, None) is not None:
                continue
            default = column.default
            if default is None:
                continue
            arg = default.arg
            value = arg() if callable(arg) else arg
            setattr(obj, column.key, value)

    def _ensure_defaults(self, obj: Any):
        if getattr(obj, 'id', None) is None:
            obj.id = uuid4()
        now = datetime.now(timezone.utc)
        if getattr(obj, 'created_at', None) is None:
            obj.created_at = now
        if getattr(obj, 'updated_at', None) is None:
            obj.updated_at = now
        self._apply_model_defaults(obj)

    def _link_relationships(self, obj: Any):
        if isinstance(obj, Draft):
            obj.content_task = self.get(ContentTask, obj.content_task_id)
        elif isinstance(obj, ContentTask):
            obj.project = self.get(Project, obj.project_id)
        elif isinstance(obj, TelegramChannel):
            obj.project = self.get(Project, obj.project_id)
        elif isinstance(obj, Publication):
            obj.draft = self.get(Draft, obj.draft_id)
            obj.telegram_channel = self.get(TelegramChannel, obj.telegram_channel_id)

    def add(self, obj: Any):
        self._ensure_defaults(obj)
        self._link_relationships(obj)
        items = self.storage[type(obj)]
        if obj not in items:
            items.append(obj)

    def commit(self):
        return None

    def refresh(self, obj: Any):
        obj.updated_at = datetime.now(timezone.utc)
        self._ensure_defaults(obj)
        self._link_relationships(obj)
        return None

    def close(self):
        return None

    def query(self, model: type):
        return FakeQuery(self.storage.get(model, []))

    def get(self, model: type, obj_id: UUID):
        lookup = str(obj_id)
        for item in self.storage.get(model, []):
            item_id = getattr(item, 'id', None)
            if item_id == obj_id or str(item_id) == lookup:
                return item
        return None


@pytest.fixture()
def fake_db():
    return FakeSession()


@pytest.fixture()
def client(fake_db: FakeSession):
    def override_get_db():
        try:
            yield fake_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    default_headers = {
        "x-telegram-user-id": "test-user-1",
        "x-telegram-username": "testuser",
        "x-telegram-first-name": "Test",
        "x-telegram-last-name": "User",
    }
    with TestClient(app, headers=default_headers) as test_client:
        yield test_client
    app.dependency_overrides.clear()
