from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from app.bot.backend_bridge import BotBackendBridge
from app.schemas.project import ProjectCreate
from app.services.identity import TelegramIdentity
from app.services.project_service import list_projects_for_owner


class QuerySpy:
    def __init__(self, rows, *, scalar_value=None):
        self.rows = list(rows)
        self.scalar_value = scalar_value
        self.filter_calls = 0
        self.join_calls = 0
        self.all_calls = 0
        self.scalar_calls = 0
        self.options_calls = 0

    def filter(self, *_args, **_kwargs):
        self.filter_calls += 1
        return self

    def join(self, *_args, **_kwargs):
        self.join_calls += 1
        return self

    def options(self, *_args, **_kwargs):
        self.options_calls += 1
        return self

    def all(self):
        self.all_calls += 1
        return list(self.rows)

    def scalar(self):
        self.scalar_calls += 1
        return self.scalar_value


class RealishSessionSpy:
    def __init__(self, query_map):
        self.query_map = query_map
        self.requested = []

    def query(self, *models):
        key = tuple(models)
        self.requested.append(key)
        return self.query_map[key]


def _bootstrap_bridge(fake_db):
    bridge = BotBackendBridge(fake_db, TelegramIdentity(telegram_user_id='perf-user', telegram_username='perf'))
    project = bridge.create_project(ProjectCreate(name='Perf Project', language='ru'))
    bridge.connect_channel(project.id, 'Perf Channel', 'perf_channel')
    plan = bridge.create_content_plan(project.id, start_date=date(2026, 3, 16), end_date=date(2026, 3, 22))
    task = bridge.create_task(project.id, 'Perf task', content_plan_id=plan.id)
    draft = bridge.create_draft(task.id, 'Perf draft text', version=1)
    draft = bridge.approve_draft(draft.id)
    publication = bridge.create_publication(draft.id, bridge.my_channels()[0].id)
    return bridge, project, draft, publication


def test_list_projects_for_owner_uses_db_filter_when_available(fake_db):
    owner_id = uuid4()
    query = QuerySpy(rows=['kept'])
    db = RealishSessionSpy(query_map={})
    from app.models.project import Project

    db.query_map[(Project,)] = query

    rows = list_projects_for_owner(db, owner_id)

    assert rows == ['kept']
    assert query.filter_calls == 1
    assert query.all_calls == 1


def test_bot_bridge_hot_paths_use_db_side_filters_and_counts(fake_db):
    bridge, project, _draft, _publication = _bootstrap_bridge(fake_db)

    from app.models.agent_profile import AgentProfile
    from app.models.content_plan import ContentPlan
    from app.models.content_task import ContentTask
    from app.models.draft import Draft
    from app.models.project import Project
    from app.models.publication import Publication
    from app.models.telegram_channel import TelegramChannel

    projects_query = QuerySpy(rows=[SimpleNamespace(id=project.id, name=project.name)])
    channels_query = QuerySpy(rows=[SimpleNamespace(project_id=project.id, channel_title='Perf Channel', channel_username='perf_channel', id=uuid4())])
    agents_query = QuerySpy(rows=[])
    plans_query = QuerySpy(rows=[SimpleNamespace(id=uuid4(), project_id=project.id, start_date=1, end_date=1)])
    tasks_query = QuerySpy(rows=[SimpleNamespace(id=uuid4(), project_id=project.id, content_plan_id=uuid4(), title='T')])
    drafts_query = QuerySpy(rows=[(SimpleNamespace(id=uuid4(), content_task_id=uuid4(), version=1, created_at=1), SimpleNamespace(id=uuid4(), title='T'))])
    publications_query = QuerySpy(rows=[(SimpleNamespace(id=uuid4(), draft_id=uuid4(), created_at=1), SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4(), title='T'))])
    realish_db = RealishSessionSpy(
        query_map={
            (Project,): projects_query,
            (TelegramChannel,): channels_query,
            (AgentProfile,): agents_query,
            (ContentPlan,): plans_query,
            (ContentTask,): tasks_query,
            (Draft, ContentTask): drafts_query,
            (Publication, Draft, ContentTask): publications_query,
        }
    )

    perf_bridge = object.__new__(BotBackendBridge)
    perf_bridge.db = realish_db
    perf_bridge.identity = bridge.identity
    perf_bridge.user = bridge.user
    perf_bridge.workspace = bridge.workspace

    perf_bridge.my_projects()
    perf_bridge.my_channels()
    perf_bridge.list_agents_for_project(project.id)
    perf_bridge.list_content_plans_for_project(project.id)
    perf_bridge.list_tasks_for_project(project.id)
    perf_bridge.list_drafts_for_project(project.id)
    perf_bridge.list_publications_for_project(project.id)

    assert projects_query.filter_calls >= 1
    assert channels_query.filter_calls == 1
    assert agents_query.filter_calls == 1
    assert plans_query.filter_calls == 1
    assert tasks_query.filter_calls == 1
    assert drafts_query.filter_calls == 1
    assert drafts_query.join_calls >= 1
    assert publications_query.filter_calls == 1
    assert publications_query.join_calls >= 2
