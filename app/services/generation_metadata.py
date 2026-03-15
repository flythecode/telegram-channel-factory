from __future__ import annotations

from app.models.content_task import ContentTask
from app.models.draft import Draft
from app.services.generation_service import GenerationExecutionResult


def build_task_generation_metadata(
    result: GenerationExecutionResult,
    *,
    task: ContentTask,
    draft: Draft | None = None,
    summary_scope: str = "task",
    **extra_fields,
) -> dict:
    return result.summary_metadata(
        summary_scope=summary_scope,
        project_id=str(task.project_id),
        content_task_id=str(task.id),
        draft_id=str(draft.id) if draft is not None else None,
        content_plan_id=str(task.content_plan_id) if task.content_plan_id else None,
        latest_draft_version=getattr(draft, 'version', None),
        **extra_fields,
    )


def build_publication_generation_metadata(draft: Draft, *, telegram_channel_id) -> dict | None:
    source_metadata = draft.generation_metadata or {}
    provider = source_metadata.get('provider')
    model = source_metadata.get('model')
    image_urls = source_metadata.get('image_urls')
    media = source_metadata.get('media')
    if provider is None and model is None and not source_metadata:
        return None
    return {
        'summary_scope': 'publication',
        'operation_type': source_metadata.get('operation_type'),
        'provider': provider,
        'model': model,
        'request_id': source_metadata.get('request_id'),
        'finish_reason': source_metadata.get('finish_reason'),
        'usage_summary': source_metadata.get('usage_summary') or {
            'prompt_tokens': source_metadata.get('prompt_tokens') or 0,
            'completion_tokens': source_metadata.get('completion_tokens') or 0,
            'total_tokens': source_metadata.get('total_tokens') or 0,
            'latency_ms': source_metadata.get('latency_ms'),
        },
        'cost_summary': source_metadata.get('cost_summary'),
        'source_draft_id': str(draft.id),
        'source_content_task_id': str(draft.content_task_id),
        'telegram_channel_id': str(telegram_channel_id),
        'draft_version': draft.version,
        'image_urls': image_urls if isinstance(image_urls, list) else None,
        'media': media if isinstance(media, list) else None,
    }
