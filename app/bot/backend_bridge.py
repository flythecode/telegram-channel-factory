from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.agent_profile import AgentProfile
from app.models.content_plan import ContentPlan
from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.publication import Publication
from app.models.telegram_channel import TelegramChannel
from app.schemas.channel import TelegramChannelUpdate
from app.schemas.content_plan import ContentPlanCreate, ContentPlanUpdate
from app.schemas.draft import DraftCreate, DraftUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.publication import PublicationCreate, PublicationUpdate
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
from app.services.crud import create_entity, get_entity_or_404, update_entity
from app.services.generation_events import create_generation_event
from app.services.generation_guardrails import evaluate_generation_guardrails
from app.services.generation_metadata import build_task_generation_metadata
from app.services.generation_queue import enqueue_and_process_generation_job
from app.services.generation_service import build_generation_service
from app.services.identity import TelegramIdentity, get_or_create_client_account_for_user, get_or_create_current_user, get_or_create_workspace_for_user
from app.services.project_service import create_project_for_owner, list_projects_for_owner, update_project_settings
from app.services.tariff_policy import resolve_plan_access_flag, resolve_plan_policy
from app.services.publish_service import queue_publication, update_publication_state
from app.services.workflow import approve_draft, mark_task_as_drafted, reject_draft
from app.utils.enums import DraftStatus, GenerationJobOperation, PublishMode


class BotBackendBridge:
    def __init__(self, db: Session, identity: TelegramIdentity):
        self.db = db
        self.identity = identity
        self.user = get_or_create_current_user(db, identity)
        self.workspace = get_or_create_workspace_for_user(db, self.user, identity)
        self.client_account = get_or_create_client_account_for_user(db, self.user, self.workspace, identity)

    def _uses_fake_session(self) -> bool:
        return hasattr(self.db, 'storage')

    def create_project(self, payload: ProjectCreate) -> Project:
        return create_project_for_owner(self.db, payload, self.user, self.workspace, client_account=self.client_account)

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
        projects = self.my_projects()
        project_ids = [project.id for project in projects]
        if not project_ids:
            return []
        if self._uses_fake_session():
            allowed = {str(project_id) for project_id in project_ids}
            return [channel for channel in self.db.query(TelegramChannel).all() if str(channel.project_id) in allowed]
        return self.db.query(TelegramChannel).filter(TelegramChannel.project_id.in_(project_ids)).all()

    def find_channel_by_title(self, channel_title: str) -> TelegramChannel | None:
        needle = (channel_title or '').strip().lower()
        if not needle:
            return None
        projects = {str(project.id): project for project in self.my_projects()}
        for channel in self.my_channels():
            project = projects.get(str(channel.project_id))
            candidates = {
                (channel.channel_title or '').strip().lower(),
                (channel.channel_username or '').strip().lower(),
                ('@' + channel.channel_username.strip().lower()) if channel.channel_username else '',
                (project.name or '').strip().lower() if project else '',
            }
            if needle in candidates:
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
        if self._uses_fake_session():
            agents = [agent for agent in self.db.query(AgentProfile).all() if str(agent.project_id) == str(project_id)]
        else:
            agents = self.db.query(AgentProfile).filter(AgentProfile.project_id == project_id).all()
        return sorted(agents, key=lambda item: (item.sort_order, item.priority, item.name))

    def list_content_plans_for_project(self, project_id) -> list[ContentPlan]:
        if self._uses_fake_session():
            plans = [plan for plan in self.db.query(ContentPlan).all() if str(plan.project_id) == str(project_id)]
        else:
            plans = self.db.query(ContentPlan).filter(ContentPlan.project_id == project_id).all()
        return sorted(plans, key=lambda item: (item.start_date, item.end_date, str(item.id)), reverse=True)

    def list_tasks_for_project(self, project_id) -> list[ContentTask]:
        if self._uses_fake_session():
            tasks = [task for task in self.db.query(ContentTask).all() if str(task.project_id) == str(project_id)]
        else:
            tasks = self.db.query(ContentTask).filter(ContentTask.project_id == project_id).all()
        return sorted(tasks, key=lambda item: (str(item.content_plan_id or ''), item.title, str(item.id)))

    def list_drafts_for_project(self, project_id) -> list[tuple[Draft, ContentTask | None]]:
        if self._uses_fake_session():
            task_map = {str(task.id): task for task in self.list_tasks_for_project(project_id)}
            drafts = [draft for draft in self.db.query(Draft).all() if str(draft.content_task_id) in task_map]
            drafts.sort(key=lambda item: (getattr(item, 'created_at', None), item.version, str(item.id)), reverse=True)
            return [(draft, task_map.get(str(draft.content_task_id))) for draft in drafts]

        rows = (
            self.db.query(Draft, ContentTask)
            .join(ContentTask, Draft.content_task_id == ContentTask.id)
            .filter(ContentTask.project_id == project_id)
            .options(joinedload(Draft.content_task))
            .all()
        )
        rows.sort(key=lambda item: (getattr(item[0], 'created_at', None), item[0].version, str(item[0].id)), reverse=True)
        return rows

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

    def _generate_idea_tasks(self, project: Project, *, plan: ContentPlan, missing_count: int) -> list[ContentTask]:
        if missing_count <= 0:
            return []
        generation_service = build_generation_service(self.db)
        brief = self._build_ideas_brief(project, plan=plan)
        generation_result = generation_service.generate_ideas(project.name, brief=brief, count=missing_count, project=project)
        idea_titles = self._extract_idea_titles(generation_result.output_text, fallback_brief=brief, count=missing_count)
        created_tasks: list[ContentTask] = []
        for index, title in enumerate(idea_titles, start=1):
            task = self.create_task(
                project.id,
                title,
                content_plan_id=plan.id,
                brief=f'LLM idea batch for {project.name}; item {index}.',
            )
            task.generation_metadata = build_task_generation_metadata(
                generation_result,
                task=task,
                summary_scope='task_seed',
                source_kind='idea_batch',
                source_item_index=index,
                source_item_count=len(idea_titles),
                source_content_plan_id=str(plan.id),
            )
            self.db.add(task)
            created_tasks.append(task)
        create_generation_event(self.db, generation_result, project=project)
        self.db.commit()
        return created_tasks

    @staticmethod
    def _build_ideas_brief(project: Project, *, plan: ContentPlan) -> str:
        parts = [
            f'канал {project.name}',
            f'ниша: {project.niche or project.topic or project.name}',
            f'язык: {project.language}',
            f'период плана: {plan.start_date} → {plan.end_date}',
        ]
        if project.goal:
            parts.append(f'цель: {project.goal}')
        if project.tone_of_voice:
            parts.append(f'тон: {project.tone_of_voice}')
        return '; '.join(parts)

    @staticmethod
    def _extract_idea_titles(output_text: str, *, fallback_brief: str, count: int) -> list[str]:
        ideas: list[str] = []
        for raw_line in output_text.splitlines():
            line = raw_line.strip().lstrip('-•').strip()
            if not line:
                continue
            if '. ' in line and line.split('. ', 1)[0].isdigit():
                line = line.split('. ', 1)[1].strip()
            if len(line) < 6:
                continue
            ideas.append(line[:255])
            if len(ideas) >= count:
                break
        while len(ideas) < count:
            ideas.append(f'{fallback_brief[:180]}: идея {len(ideas) + 1}')
        return ideas

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
        result = enqueue_and_process_generation_job(
            self.db,
            operation=GenerationJobOperation.REGENERATE_DRAFT,
            project_id=draft.content_task.project_id,
            content_task_id=draft.content_task_id,
            draft_id=draft.id,
            payload={},
        )
        assert result.draft is not None
        return result.draft

    def rewrite_draft(self, draft_id, rewrite_prompt: str) -> Draft:
        draft = self.get_draft(draft_id)
        result = enqueue_and_process_generation_job(
            self.db,
            operation=GenerationJobOperation.REWRITE_DRAFT,
            project_id=draft.content_task.project_id,
            content_task_id=draft.content_task_id,
            draft_id=draft.id,
            payload={'rewrite_prompt': rewrite_prompt},
        )
        assert result.draft is not None
        return result.draft

    def list_publications_for_project(self, project_id) -> list[tuple[Publication, Draft | None, ContentTask | None]]:
        if self._uses_fake_session():
            task_map = {str(task.id): task for task in self.list_tasks_for_project(project_id)}
            draft_map = {str(draft.id): (draft, task_map.get(str(draft.content_task_id))) for draft, _task in self.list_drafts_for_project(project_id)}
            publications = [publication for publication in self.db.query(Publication).all() if str(publication.draft_id) in draft_map]
            publications.sort(key=lambda item: (getattr(item, 'created_at', None), str(item.id)), reverse=True)
            return [(publication, *draft_map.get(str(publication.draft_id), (None, None))) for publication in publications]

        rows = (
            self.db.query(Publication, Draft, ContentTask)
            .join(Draft, Publication.draft_id == Draft.id)
            .join(ContentTask, Draft.content_task_id == ContentTask.id)
            .filter(ContentTask.project_id == project_id)
            .options(joinedload(Publication.draft).joinedload(Draft.content_task))
            .all()
        )
        rows.sort(key=lambda item: (getattr(item[0], 'created_at', None), str(item[0].id)), reverse=True)
        return rows

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
        if self._uses_fake_session():
            return len(self.list_agents_for_project(project_id))
        return int(self.db.query(func.count(AgentProfile.id)).filter(AgentProfile.project_id == project_id).scalar() or 0)

    def count_content_plans_for_project(self, project_id) -> int:
        if self._uses_fake_session():
            return len(self.list_content_plans_for_project(project_id))
        return int(self.db.query(func.count(ContentPlan.id)).filter(ContentPlan.project_id == project_id).scalar() or 0)

    def count_drafts_for_project(self, project_id) -> int:
        if self._uses_fake_session():
            return len(self.list_drafts_for_project(project_id))
        return int(
            self.db.query(func.count(Draft.id))
            .join(ContentTask, Draft.content_task_id == ContentTask.id)
            .filter(ContentTask.project_id == project_id)
            .scalar()
            or 0
        )

    def get_generation_status_summary(self, project_id, *, channel_id=None, draft_id=None) -> dict:
        project = self.get_project(project_id)
        channel = None
        if channel_id:
            try:
                channel = self.get_channel(channel_id)
            except Exception:
                channel = None
        guardrails = evaluate_generation_guardrails(self.db, project=project, channel=channel).metadata()
        plan = resolve_plan_policy(getattr(project, 'client_account', None) or self.client_account)
        access_flag = resolve_plan_access_flag(getattr(project, 'client_account', None) or self.client_account)

        all_jobs = self.db.query(GenerationJob).all()
        project_jobs = [job for job in all_jobs if str(getattr(job, 'project_id', '')) == str(project_id)]
        queued = [job for job in project_jobs if getattr(getattr(job, 'status', None), 'value', getattr(job, 'status', None)) == 'queued']
        processing = [job for job in project_jobs if getattr(getattr(job, 'status', None), 'value', getattr(job, 'status', None)) == 'processing']
        failed = [job for job in project_jobs if getattr(getattr(job, 'status', None), 'value', getattr(job, 'status', None)) == 'failed']
        latest_job = None
        relevant_jobs = project_jobs
        if draft_id is not None:
            relevant_jobs = [job for job in project_jobs if str(getattr(job, 'draft_id', '')) == str(draft_id)] or project_jobs
        if relevant_jobs:
            latest_job = sorted(
                relevant_jobs,
                key=lambda item: (
                    getattr(item, 'finished_at', None) or getattr(item, 'started_at', None) or getattr(item, 'queued_at', None),
                    str(item.id),
                ),
                reverse=True,
            )[0]

        latest_status = None
        latest_error = None
        if latest_job is not None:
            latest_status = getattr(getattr(latest_job, 'status', None), 'value', getattr(latest_job, 'status', None))
            latest_error = getattr(latest_job, 'error_message', None)

        client_account = getattr(project, 'client_account', None) or self.client_account
        subscription_status = getattr(getattr(client_account, 'subscription_status', None), 'value', getattr(client_account, 'subscription_status', None))
        current_period_end = getattr(client_account, 'current_period_end', None)
        trial_ends_at = getattr(client_account, 'trial_ends_at', None)
        active_window = None
        client_guardrails = guardrails.get('client') or {}
        client_windows = client_guardrails.get('windows') or []
        for window_name in ('monthly', 'billing_period', 'daily'):
            active_window = next((item for item in client_windows if item.get('window') == window_name), None)
            if active_window:
                break
        quota_limit = None
        quota_used = 0
        if active_window and active_window.get('generation_quota_limit'):
            quota_limit = active_window.get('generation_quota_limit')
            quota_used = active_window.get('total_generations', 0)
        elif client_guardrails.get('generation_quota_limit'):
            quota_limit = client_guardrails.get('generation_quota_limit')
            quota_used = client_guardrails.get('total_generations', 0)
        quota_remaining = None if quota_limit is None else max(int(quota_limit) - int(quota_used or 0), 0)
        period_end = None
        if active_window and active_window.get('period_end'):
            period_end = active_window.get('period_end')
        elif current_period_end is not None:
            period_end = current_period_end.isoformat()
        elif trial_ends_at is not None:
            period_end = trial_ends_at.isoformat()

        return {
            'queue': {
                'queued': len(queued),
                'processing': len(processing),
                'failed': len(failed),
                'latest_status': latest_status,
                'latest_error': latest_error,
            },
            'guardrails': guardrails,
            'plan': {
                'code': plan.plan_code,
                'label': plan.label,
                'access_flag': access_flag,
                'status': subscription_status or access_flag,
                'status_label': 'активен' if access_flag == 'paid' else ('триал' if access_flag == 'trial' else 'не оплачен'),
                'generation_limit': plan.included_generations,
                'generation_used': quota_used,
                'generation_remaining': quota_remaining,
                'period_end': period_end,
                'is_blocked': bool(guardrails.get('hard_stop_reached')) or access_flag == 'unpaid',
                'block_reason': '; '.join(guardrails.get('blocking_reasons') or []) or (None if access_flag != 'unpaid' else 'подписка не оплачена'),
            },
        }

    def build_draft_generation_status(self, draft: Draft, *, channel_id=None) -> dict:
        summary = self.get_generation_status_summary(draft.content_task.project_id, channel_id=channel_id, draft_id=draft.id)
        metadata = draft.generation_metadata or {}
        failover = metadata.get('failover') or {}
        return {
            **summary,
            'generation': {
                'provider': metadata.get('provider'),
                'model': metadata.get('model'),
                'finish_reason': metadata.get('finish_reason'),
                'request_id': metadata.get('request_id'),
                'failover_activated': bool(failover.get('activated')),
                'failover_outcome': failover.get('outcome'),
                'fallback_provider': failover.get('fallback_provider'),
                'primary_error_message': ((failover.get('primary_error') or {}).get('message')),
            },
        }

    def create_content_plan(self, project_id, period_type='week', start_date=None, end_date=None) -> ContentPlan:
        payload = ContentPlanCreate(
            period_type=period_type,
            start_date=start_date or date.today(),
            end_date=end_date or (date.today() + timedelta(days=6)),
            status='generated',
        )
        project = self.get_project(project_id)
        plan = create_entity(self.db, ContentPlan, payload, project_id=project_id)
        result = enqueue_and_process_generation_job(
            self.db,
            operation=GenerationJobOperation.GENERATE_CONTENT_PLAN,
            project_id=project.id,
            content_plan_id=plan.id,
            payload={'status': payload.status},
        )
        assert result.content_plan is not None
        return result.content_plan

    def create_task(self, project_id, title: str, content_plan_id=None, brief: str | None = None) -> ContentTask:
        return create_entity(
            self.db,
            ContentTask,
            type('Payload', (), {'model_dump': lambda self_: {'title': title, 'content_plan_id': content_plan_id, 'brief': brief}})(),
            project_id=project_id,
        )

    def create_draft(self, task_id, text: str, version: int = 1, created_by_agent: str | None = None) -> Draft:
        task = get_entity_or_404(self.db, ContentTask, task_id, 'Task not found')
        result = enqueue_and_process_generation_job(
            self.db,
            operation=GenerationJobOperation.CREATE_DRAFT,
            project_id=task.project_id,
            content_task_id=task.id,
            payload=DraftCreate(text=text, version=version, created_by_agent=created_by_agent).model_dump(),
        )
        assert result.draft is not None
        return result.draft

    def ensure_sample_pipeline(self, project_id, *, tasks_count: int = 10, drafts_count: int = 3) -> tuple[ContentPlan, list[ContentTask], list[Draft]]:
        plans = self.list_content_plans_for_project(project_id)
        if plans:
            plan = plans[0]
        else:
            today = date.today()
            start_date = today + timedelta(days=(7 - today.weekday()) % 7)
            end_date = start_date + timedelta(days=6)
            plan = self.create_content_plan(project_id, start_date=start_date, end_date=end_date)

        tasks = [task for task in self.list_tasks_for_project(project_id) if str(task.content_plan_id) == str(plan.id)]
        if len(tasks) < tasks_count:
            project = self.get_project(project_id)
            generated_tasks = self._generate_idea_tasks(project, plan=plan, missing_count=tasks_count - len(tasks))
            tasks.extend(generated_tasks)

        existing_drafts = self.list_drafts_for_project(project_id)
        draft_task_ids = {str(draft.content_task_id) for draft, _task in existing_drafts}
        created_drafts: list[Draft] = []
        for task in tasks:
            if len(draft_task_ids) >= drafts_count:
                break
            if str(task.id) in draft_task_ids:
                continue
            draft = self.create_draft(
                task.id,
                text=(
                    f'Черновик для темы "{task.title}".\n\n'
                    f'Ключевой угол: {task.brief or "короткий полезный пост"}.\n'
                    '1. Зацепка\n'
                    '2. Основная мысль\n'
                    '3. Практический вывод'
                ),
                version=1,
            )
            created_drafts.append(draft)
            draft_task_ids.add(str(task.id))

        refreshed_tasks = [task for task in self.list_tasks_for_project(project_id) if str(task.content_plan_id) == str(plan.id)]
        refreshed_drafts = [draft for draft, _task in self.list_drafts_for_project(project_id)]
        return plan, refreshed_tasks, refreshed_drafts
