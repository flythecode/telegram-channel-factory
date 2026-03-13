from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.agent_profile import AgentProfile
from app.models.content_plan import ContentPlan
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.models.project import Project
from app.models.publication import Publication
from app.models.telegram_channel import TelegramChannel
from app.schemas.channel import TelegramChannelUpdate
from app.schemas.content_plan import ContentPlanCreate
from app.schemas.draft import DraftUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.publication import PublicationCreate, PublicationUpdate
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
from app.services.crud import create_entity, get_entity_or_404, update_entity
from app.services.identity import TelegramIdentity, get_or_create_current_user, get_or_create_workspace_for_user
from app.services.project_service import create_project_for_owner, list_projects_for_owner, update_project_settings
from app.services.publish_service import queue_publication, update_publication_state
from app.services.workflow import approve_draft, reject_draft
from app.utils.enums import DraftStatus, PublishMode


class BotBackendBridge:
    def __init__(self, db: Session, identity: TelegramIdentity):
        self.db = db
        self.identity = identity
        self.user = get_or_create_current_user(db, identity)
        self.workspace = get_or_create_workspace_for_user(db, self.user, identity)

    def create_project(self, payload: ProjectCreate) -> Project:
        return create_project_for_owner(self.db, payload, self.user, self.workspace)

    def my_projects(self) -> list[Project]:
        return list_projects_for_owner(self.db, self.user.id)

    def update_project(self, project_id, payload: ProjectUpdate) -> Project:
        project = get_entity_or_404(self.db, Project, project_id, 'Project not found')
        return update_project_settings(self.db, project, payload, created_by_user_id=self.user.id)

    def apply_preset(self, project_id, preset_code: str) -> list[AgentProfile]:
        ensure_default_presets(self.db)
        return apply_preset_to_project(self.db, project_id, preset_code)

    def connect_channel(self, project_id, channel_title: str, channel_username: str | None = None) -> TelegramChannel:
        return create_entity(
            self.db,
            TelegramChannel,
            type('Payload', (), {
                'model_dump': lambda self_: {
                    'channel_title': channel_title,
                    'channel_username': channel_username,
                    'is_connected': True,
                    'bot_is_admin': True,
                    'can_post_messages': True,
                }
            })(),
            project_id=project_id,
        )

    def my_channels(self) -> list[TelegramChannel]:
        project_ids = {project.id for project in self.my_projects()}
        return [channel for channel in self.db.query(TelegramChannel).all() if channel.project_id in project_ids]

    def find_channel_by_title(self, channel_title: str) -> TelegramChannel | None:
        for channel in self.my_channels():
            if channel.channel_title == channel_title:
                return channel
        return None

    def get_channel(self, channel_id) -> TelegramChannel:
        return get_entity_or_404(self.db, TelegramChannel, channel_id, 'Channel not found')

    def update_channel(self, channel_id, payload: TelegramChannelUpdate) -> TelegramChannel:
        channel = self.get_channel(channel_id)
        return update_entity(self.db, channel, payload)

    def update_channel_mode(self, channel_id, publish_mode: str) -> TelegramChannel:
        return self.update_channel(channel_id, TelegramChannelUpdate(publish_mode=PublishMode(publish_mode)))

    def get_project(self, project_id) -> Project:
        return get_entity_or_404(self.db, Project, project_id, 'Project not found')

    def list_agents_for_project(self, project_id) -> list[AgentProfile]:
        agents = [agent for agent in self.db.query(AgentProfile).all() if str(agent.project_id) == str(project_id)]
        return sorted(agents, key=lambda item: (item.sort_order, item.priority, item.name))

    def list_content_plans_for_project(self, project_id) -> list[ContentPlan]:
        plans = [plan for plan in self.db.query(ContentPlan).all() if str(plan.project_id) == str(project_id)]
        return sorted(plans, key=lambda item: (item.start_date, item.end_date, str(item.id)), reverse=True)

    def list_tasks_for_project(self, project_id) -> list[ContentTask]:
        tasks = [task for task in self.db.query(ContentTask).all() if str(task.project_id) == str(project_id)]
        return sorted(tasks, key=lambda item: (str(item.content_plan_id or ''), item.title, str(item.id)))

    def list_drafts_for_project(self, project_id) -> list[tuple[Draft, ContentTask | None]]:
        task_map = {str(task.id): task for task in self.list_tasks_for_project(project_id)}
        drafts = [draft for draft in self.db.query(Draft).all() if str(draft.content_task_id) in task_map]
        drafts.sort(key=lambda item: (getattr(item, 'created_at', None), item.version, str(item.id)), reverse=True)
        return [(draft, task_map.get(str(draft.content_task_id))) for draft in drafts]

    def find_draft_for_project_by_title(self, project_id, title: str) -> tuple[Draft, ContentTask | None] | None:
        for draft, task in self.list_drafts_for_project(project_id):
            if task is not None and task.title == title:
                return draft, task
        return None

    def get_draft(self, draft_id) -> Draft:
        return get_entity_or_404(self.db, Draft, draft_id, 'Draft not found')

    def approve_draft(self, draft_id) -> Draft:
        draft = self.get_draft(draft_id)
        task = draft.content_task
        approve_draft(task, draft)
        self.db.add(task)
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def reject_draft(self, draft_id) -> Draft:
        draft = self.get_draft(draft_id)
        task = draft.content_task
        reject_draft(task, draft)
        self.db.add(task)
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def edit_draft(self, draft_id, new_text: str) -> Draft:
        draft = self.get_draft(draft_id)
        return update_entity(self.db, draft, DraftUpdate(text=new_text, status=DraftStatus.EDITED))

    def regenerate_draft(self, draft_id) -> Draft:
        draft = self.get_draft(draft_id)
        return update_entity(self.db, draft, DraftUpdate(text=draft.text + '\n\n[Regenerated]', status=DraftStatus.EDITED))

    def list_publications_for_project(self, project_id) -> list[tuple[Publication, Draft | None, ContentTask | None]]:
        task_map = {str(task.id): task for task in self.list_tasks_for_project(project_id)}
        draft_map = {str(draft.id): (draft, task_map.get(str(draft.content_task_id))) for draft, _task in self.list_drafts_for_project(project_id)}
        publications = [publication for publication in self.db.query(Publication).all() if str(publication.draft_id) in draft_map]
        publications.sort(key=lambda item: (getattr(item, 'created_at', None), str(item.id)), reverse=True)
        return [(publication, *draft_map.get(str(publication.draft_id), (None, None))) for publication in publications]

    def find_publication_for_project_by_title(self, project_id, title: str) -> tuple[Publication, Draft | None, ContentTask | None] | None:
        for publication, draft, task in self.list_publications_for_project(project_id):
            if task is not None and task.title == title:
                return publication, draft, task
        return None

    def get_publication(self, publication_id) -> Publication:
        return get_entity_or_404(self.db, Publication, publication_id, 'Publication not found')

    def create_publication(self, draft_id, telegram_channel_id, scheduled_for=None) -> Publication:
        return queue_publication(self.db, draft_id, PublicationCreate(telegram_channel_id=telegram_channel_id, scheduled_for=scheduled_for))

    def publish_now(self, publication_id) -> Publication:
        return update_publication_state(self.db, publication_id, PublicationUpdate(status='sending', scheduled_for=None, published_at=datetime.now(timezone.utc)))

    def cancel_publication(self, publication_id) -> Publication:
        return update_publication_state(self.db, publication_id, PublicationUpdate(status='canceled'))

    def schedule_publication(self, publication_id, scheduled_for: datetime) -> Publication:
        return update_publication_state(self.db, publication_id, PublicationUpdate(status='queued', scheduled_for=scheduled_for))

    def count_agents_for_project(self, project_id) -> int:
        return len(self.list_agents_for_project(project_id))

    def count_content_plans_for_project(self, project_id) -> int:
        return len(self.list_content_plans_for_project(project_id))

    def count_drafts_for_project(self, project_id) -> int:
        return len(self.list_drafts_for_project(project_id))

    def create_content_plan(self, project_id, period_type='week', start_date=None, end_date=None) -> ContentPlan:
        payload = ContentPlanCreate(
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
            status='generated',
        )
        return create_entity(self.db, ContentPlan, payload, project_id=project_id)

    def create_task(self, project_id, title: str, content_plan_id=None) -> ContentTask:
        return create_entity(
            self.db,
            ContentTask,
            type('Payload', (), {'model_dump': lambda self_: {'title': title, 'content_plan_id': content_plan_id}})(),
            project_id=project_id,
        )
