from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.models.generation_job import GenerationJob

logger = logging.getLogger(__name__)

_PROVIDER_HEALTH: dict[str, dict[str, Any]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_generation_event(event: str, **fields: Any) -> None:
    logger.info(event, extra={'event': event, **fields})


def emit_generation_warning(event: str, **fields: Any) -> None:
    logger.warning(event, extra={'event': event, **fields})


def emit_generation_exception(event: str, **fields: Any) -> None:
    logger.exception(event, extra={'event': event, **fields})


def build_job_trace(job: GenerationJob | None) -> dict[str, Any]:
    if job is None:
        return {}
    return {
        'job_id': str(job.id),
        'job_operation': getattr(job.operation, 'value', str(job.operation)),
        'job_status': getattr(job.status, 'value', str(job.status)),
        'job_priority': job.priority,
        'project_id': str(job.project_id) if job.project_id is not None else None,
        'client_account_id': str(job.client_account_id) if job.client_account_id is not None else None,
        'content_task_id': str(job.content_task_id) if job.content_task_id is not None else None,
        'draft_id': str(job.draft_id) if job.draft_id is not None else None,
        'content_plan_id': str(job.content_plan_id) if job.content_plan_id is not None else None,
        'lease_token': job.lease_token,
    }


def queue_depth_snapshot(jobs: list[GenerationJob]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    operation_counts: dict[str, int] = {}
    project_counts: dict[str, int] = {}
    urgent_queued = 0
    top_queued_priority = None
    for job in jobs:
        status = getattr(job.status, 'value', str(job.status))
        operation = getattr(job.operation, 'value', str(job.operation))
        project_key = str(job.project_id) if job.project_id is not None else 'unscoped'
        status_counts[status] = status_counts.get(status, 0) + 1
        operation_counts[operation] = operation_counts.get(operation, 0) + 1
        project_counts[project_key] = project_counts.get(project_key, 0) + 1
        if status == 'queued':
            if top_queued_priority is None or job.priority < top_queued_priority:
                top_queued_priority = job.priority
            if job.priority == 0:
                urgent_queued += 1
    return {
        'jobs_total': len(jobs),
        'status_counts': status_counts,
        'operation_counts': operation_counts,
        'projects_in_queue': len(project_counts),
        'urgent_queued': urgent_queued,
        'top_queued_priority': top_queued_priority,
    }


def provider_health_snapshot(provider: str | None = None) -> dict[str, Any]:
    if provider is None:
        return {key: value.copy() for key, value in _PROVIDER_HEALTH.items()}
    return (_PROVIDER_HEALTH.get(provider) or {}).copy()


def record_provider_health(
    provider: str,
    *,
    model: str | None = None,
    ok: bool,
    retryable: bool | None = None,
    status_code: int | None = None,
    latency_ms: int | None = None,
    error_message: str | None = None,
    request_id: str | None = None,
    failover: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = _PROVIDER_HEALTH.setdefault(
        provider,
        {
            'provider': provider,
            'successes': 0,
            'failures': 0,
            'retryable_failures': 0,
            'last_status': 'unknown',
            'last_status_code': None,
            'last_error': None,
            'last_latency_ms': None,
            'last_request_id': None,
            'last_model': None,
            'last_failover_outcome': None,
            'updated_at': None,
        },
    )
    if ok:
        state['successes'] += 1
        state['last_status'] = 'ok'
        state['last_error'] = None
    else:
        state['failures'] += 1
        state['last_status'] = 'error'
        state['last_error'] = error_message
        if retryable:
            state['retryable_failures'] += 1
    state['last_status_code'] = status_code
    state['last_latency_ms'] = latency_ms
    state['last_request_id'] = request_id
    state['last_model'] = model
    if failover is not None:
        state['last_failover_outcome'] = failover.get('outcome')
    state['updated_at'] = _utc_now()
    return state.copy()


def reset_provider_health() -> None:
    _PROVIDER_HEALTH.clear()
