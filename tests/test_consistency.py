from app.api.v1 import agents, channels, content_plans, drafts, projects, publications, tasks
from app.models.agent_profile import AgentProfile
from app.models.content_plan import ContentPlan
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.models.project import Project
from app.models.publication import Publication
from app.models.telegram_channel import TelegramChannel
from app.schemas.agent import AgentProfileRead
from app.schemas.channel import TelegramChannelRead
from app.schemas.content_plan import ContentPlanRead
from app.schemas.draft import DraftRead
from app.schemas.project import ProjectRead
from app.schemas.publication import PublicationRead
from app.schemas.task import ContentTaskRead


ENTITY_MATRIX = [
    (Project, ProjectRead, projects.router, 'projects'),
    (TelegramChannel, TelegramChannelRead, channels.router, 'channels'),
    (AgentProfile, AgentProfileRead, agents.router, 'agents'),
    (ContentPlan, ContentPlanRead, content_plans.router, 'content-plans'),
    (ContentTask, ContentTaskRead, tasks.router, 'tasks'),
    (Draft, DraftRead, drafts.router, 'drafts'),
    (Publication, PublicationRead, publications.router, 'publications'),
]



def _model_field_names(model_cls):
    return {column.key for column in model_cls.__table__.columns}



def _schema_field_names(schema_cls):
    return set(schema_cls.model_fields.keys())



def test_all_entities_have_model_schema_and_router_binding():
    for model_cls, schema_cls, router, expected_tag in ENTITY_MATRIX:
        assert model_cls is not None
        assert schema_cls is not None
        assert router is not None
        assert expected_tag in router.tags



def test_read_schemas_match_model_columns_plus_common_fields():
    common = {'id', 'created_at', 'updated_at'}
    for model_cls, schema_cls, _router, _tag in ENTITY_MATRIX:
        model_fields = _model_field_names(model_cls)
        schema_fields = _schema_field_names(schema_cls)
        assert schema_fields == model_fields | common



def test_routers_expose_at_least_one_route_per_entity():
    for _model_cls, _schema_cls, router, _tag in ENTITY_MATRIX:
        assert len(router.routes) >= 1
