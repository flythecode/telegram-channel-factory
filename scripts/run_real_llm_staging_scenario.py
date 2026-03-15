from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.models.workspace import Workspace
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
from app.services.generation_events import create_generation_event, summarize_generation_usage
from app.services.generation_queue import enqueue_and_process_generation_job
from app.services.generation_service import build_generation_service
from app.utils.enums import GenerationJobOperation, SubscriptionStatus


class ScenarioError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def validate_runtime() -> dict:
    llm_secret = Path(settings.llm_api_key_file).resolve() if settings.llm_api_key_file else None
    telegram_secret = Path(settings.telegram_bot_token_file).resolve() if settings.telegram_bot_token_file else None

    _require(settings.app_env == 'staging', 'APP_ENV must be staging')
    _require(settings.runtime_mode == 'demo', 'RUNTIME_MODE must be demo')
    _require(settings.publisher_backend == 'stub', 'PUBLISHER_BACKEND must stay stub for real-LLM staging scenario')
    _require(settings.llm_provider != 'stub', 'LLM_PROVIDER must be a real provider for this scenario')
    _require(bool(settings.llm_api_key_file), 'LLM_API_KEY_FILE is required for a separate staging provider key')
    _require(llm_secret is not None and llm_secret.is_file(), 'LLM_API_KEY_FILE must point to an existing secret file')
    if telegram_secret is not None:
        _require(llm_secret != telegram_secret, 'LLM_API_KEY_FILE must not match TELEGRAM_BOT_TOKEN_FILE')

    return {
        'app_env': settings.app_env,
        'runtime_mode': settings.runtime_mode,
        'publisher_backend': settings.publisher_backend,
        'llm_provider': settings.llm_provider,
        'llm_model_default': settings.llm_model_default,
        'llm_api_key_file': str(llm_secret),
        'telegram_bot_token_file': str(telegram_secret) if telegram_secret is not None else None,
    }


def main() -> None:
    runtime_summary = validate_runtime()
    db = SessionLocal()
    try:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        unique = uuid4().hex[:8]

        user = User(email=f'staging-real-llm-{unique}@example.com', telegram_user_id=f'staging-real-llm-{unique}')
        db.add(user)
        db.commit()
        db.refresh(user)

        workspace = Workspace(
            owner_user_id=user.id,
            created_by_user_id=user.id,
            name=f'Real LLM Staging Workspace {stamp}',
            slug=f'real-llm-staging-{unique}',
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        account = ClientAccount(
            owner_user_id=user.id,
            workspace_id=workspace.id,
            name=f'Real LLM Staging Account {stamp}',
            subscription_plan_code='business',
            subscription_status=SubscriptionStatus.ACTIVE,
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        project = Project(
            workspace_id=workspace.id,
            client_account_id=account.id,
            owner_user_id=user.id,
            created_by_user_id=user.id,
            name=f'Real LLM Staging Project {stamp}',
            language='ru',
            topic='AI agents and crypto analytics',
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        channel = TelegramChannel(
            project_id=project.id,
            channel_title=f'Real LLM Staging Channel {stamp}',
            channel_username=f'staging_real_llm_{unique}',
            channel_id=f'@staging_real_llm_{unique}',
            is_active=True,
            is_connected=True,
            bot_is_admin=True,
            can_post_messages=True,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)

        ensure_default_presets(db)
        apply_preset_to_project(db, project.id, 'starter_3')
        db.refresh(project)

        generation_service = build_generation_service(db)
        ideas_result = generation_service.generate_ideas(
            project.name,
            brief='Нужны полезные и конкретные идеи для Telegram-канала про ИИ-агентов и крипто-аналитику.',
            count=3,
            project=project,
        )
        create_generation_event(db, ideas_result, project=project, channel=channel, status='succeeded')
        db.commit()

        task = ContentTask(
            project_id=project.id,
            title='Реальный staging draft smoke',
            brief='Сделай короткий Telegram-пост про практическое применение ИИ-агентов в аналитике.',
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        draft_result = enqueue_and_process_generation_job(
            db,
            operation=GenerationJobOperation.CREATE_DRAFT,
            project_id=project.id,
            content_task_id=task.id,
            payload={'text': 'Seed draft text', 'version': 1},
        )
        db.commit()

        draft = draft_result.draft
        _require(draft is not None, 'Draft generation did not produce a draft')

        ideas_meta = ideas_result.metadata()
        draft_meta = draft.generation_metadata or {}

        _require(ideas_meta.get('provider') not in {None, 'stub'}, 'Ideas generation stayed on stub or has no provider')
        _require(draft_meta.get('provider') not in {None, 'stub'}, 'Draft generation stayed on stub or has no provider')
        _require(bool(ideas_meta.get('request_id')), 'Ideas generation request_id missing')
        _require(bool(draft_meta.get('request_id')), 'Draft generation request_id missing')
        _require(bool(ideas_meta.get('model')), 'Ideas generation model missing')
        _require(bool(draft_meta.get('model')), 'Draft generation model missing')
        _require(int(ideas_meta.get('latency_ms') or 0) > 0, 'Ideas generation latency missing')
        _require(int(draft_meta.get('latency_ms') or 0) > 0, 'Draft generation latency missing')

        usage = summarize_generation_usage(db)
        usage_by_operation = {item.operation_type: item for item in usage if item.project_id == project.id}
        _require('ideas' in usage_by_operation, 'Usage summary missing ideas operation')
        _require('draft' in usage_by_operation, 'Usage summary missing draft operation')
        _require(usage_by_operation['ideas'].successful_events_count >= 1, 'Ideas usage summary has no successful events')
        _require(usage_by_operation['draft'].successful_events_count >= 1, 'Draft usage summary has no successful events')

        result = {
            'status': 'pass',
            'runtime': runtime_summary,
            'project_id': str(project.id),
            'channel_id': str(channel.id),
            'task_id': str(task.id),
            'draft_id': str(draft.id),
            'ideas': {
                'provider': ideas_meta.get('provider'),
                'model': ideas_meta.get('model'),
                'request_id': ideas_meta.get('request_id'),
                'latency_ms': ideas_meta.get('latency_ms'),
                'total_tokens': ideas_meta.get('total_tokens'),
            },
            'draft': {
                'provider': draft_meta.get('provider'),
                'model': draft_meta.get('model'),
                'request_id': draft_meta.get('request_id'),
                'latency_ms': draft_meta.get('latency_ms'),
                'total_tokens': (draft_meta.get('usage_summary') or {}).get('total_tokens'),
            },
            'usage_summary': {
                operation: {
                    'events_count': item.events_count,
                    'successful_events_count': item.successful_events_count,
                    'total_tokens': item.total_tokens,
                    'total_cost_usd': str(item.total_cost_usd),
                }
                for operation, item in sorted(usage_by_operation.items())
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == '__main__':
    main()
