from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.generation_job import GenerationJob
from app.services.generation_observability import emit_generation_event, emit_generation_warning, provider_health_snapshot, queue_depth_snapshot
from app.services.generation_queue import claim_generation_job_by_id, list_generation_jobs, process_claimed_generation_job
from app.utils.enums import GenerationJobStatus


@dataclass(slots=True)
class GenerationWorkerSlotSummary:
    slot_index: int
    project_id: str
    processed: int
    failed: int
    job_ids: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class GenerationWorkerPoolSummary:
    queued_seen: int
    projects_seen: int
    slots_used: int
    processed: int
    failed: int
    started_at: str
    finished_at: str
    duration_ms: float
    slots: list[GenerationWorkerSlotSummary]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload['slots'] = [slot.to_dict() for slot in self.slots]
        return payload


def process_generation_worker_pool(
    db: Session,
    *,
    pool_size: int = 4,
    batch_limit: int | None = None,
) -> GenerationWorkerPoolSummary:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()
    all_jobs = list_generation_jobs(db)
    queued_jobs = [job for job in all_jobs if job.status == GenerationJobStatus.QUEUED]
    projects = _group_jobs_by_project(queued_jobs)
    emit_generation_event(
        'generation worker pool batch started',
        pool_size=max(pool_size, 1),
        batch_limit=batch_limit,
        queue_snapshot=queue_depth_snapshot(all_jobs),
        provider_health=provider_health_snapshot(),
    )
    scheduled_jobs = _select_jobs_for_batch(
        queued_jobs,
        all_jobs=all_jobs,
        pool_size=max(pool_size, 1),
        batch_limit=batch_limit,
        now=started_at,
    )
    slot_buckets = _assign_jobs_to_slots(scheduled_jobs, pool_size=max(pool_size, 1))

    processed = 0
    failed = 0
    slot_summaries: list[GenerationWorkerSlotSummary] = []

    for slot_index, slot_jobs in enumerate(slot_buckets, start=1):
        if not slot_jobs:
            continue
        slot_processed = 0
        slot_failed = 0
        slot_job_ids: list[str] = []
        slot_project_ids: list[str] = []

        for scheduled_job in slot_jobs:
            claimed_job = claim_generation_job_by_id(db, job_id=scheduled_job.id)
            if claimed_job is None:
                continue
            project_key = _project_key(claimed_job)
            if project_key not in slot_project_ids:
                slot_project_ids.append(project_key)
            try:
                process_claimed_generation_job(db, claimed_job)
                processed += 1
                slot_processed += 1
            except Exception as exc:
                failed += 1
                slot_failed += 1
                emit_generation_warning(
                    'generation worker pool job failed',
                    slot_index=slot_index,
                    job_id=str(claimed_job.id),
                    project_id=project_key,
                    error=str(exc),
                )
            finally:
                slot_job_ids.append(str(claimed_job.id))

        slot_summaries.append(
            GenerationWorkerSlotSummary(
                slot_index=slot_index,
                project_id=','.join(slot_project_ids),
                processed=slot_processed,
                failed=slot_failed,
                job_ids=slot_job_ids,
            )
        )

    finished_at = datetime.now(timezone.utc)
    summary = GenerationWorkerPoolSummary(
        queued_seen=len(queued_jobs),
        projects_seen=len(projects),
        slots_used=len(slot_summaries),
        processed=processed,
        failed=failed,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_ms=round((perf_counter() - started_perf) * 1000, 2),
        slots=slot_summaries,
    )
    emit_generation_event(
        'generation worker pool batch completed',
        **summary.to_dict(),
        provider_health=provider_health_snapshot(),
    )
    return summary



def _group_jobs_by_project(jobs: list[GenerationJob]) -> dict[str, list[GenerationJob]]:
    grouped: dict[str, list[GenerationJob]] = defaultdict(list)
    for job in jobs:
        grouped[_project_key(job)].append(job)
    for project_jobs in grouped.values():
        project_jobs.sort(key=lambda item: (item.priority, item.queued_at, str(item.id)))
    return dict(
        sorted(
            grouped.items(),
            key=lambda item: (
                min(job.priority for job in item[1]),
                min(job.queued_at for job in item[1]),
                item[0],
            ),
        )
    )



def _select_jobs_for_batch(
    queued_jobs: list[GenerationJob],
    *,
    all_jobs: list[GenerationJob],
    pool_size: int,
    batch_limit: int | None,
    now: datetime,
) -> list[GenerationJob]:
    effective_batch_limit = batch_limit if batch_limit is not None else len(queued_jobs)
    effective_batch_limit = min(effective_batch_limit, settings.generation_job_batch_limit)
    if effective_batch_limit <= 0:
        return []

    active_by_project = _count_active_jobs(all_jobs, scope='project')
    active_by_client = _count_active_jobs(all_jobs, scope='client')
    rate_state = _build_rate_state(all_jobs, now=now)
    slots: list[list[GenerationJob]] = [[] for _ in range(pool_size)]
    project_slot_index: dict[str, int] = {}
    client_slot_usage: dict[str, set[int]] = defaultdict(set)
    selected: list[GenerationJob] = []

    for job in queued_jobs:
        if len(selected) >= effective_batch_limit:
            break
        project_key = _project_key(job)
        client_key = _client_key(job)
        if active_by_project[project_key] >= settings.generation_project_concurrency_limit:
            continue
        if active_by_client[client_key] >= settings.generation_client_concurrency_limit:
            continue
        if not _within_rate_limits(job, rate_state=rate_state):
            continue

        if project_key in project_slot_index:
            slot_index = project_slot_index[project_key]
        else:
            slot_index = _select_slot_for_job(slots, client_key=client_key, client_slot_usage=client_slot_usage)
            if slot_index is None:
                continue
            project_slot_index[project_key] = slot_index

        slots[slot_index].append(job)
        client_slot_usage[client_key].add(slot_index)
        _consume_rate_limits(job, rate_state=rate_state)
        selected.append(job)

    return selected



def _count_active_jobs(all_jobs: list[GenerationJob], *, scope: str) -> dict[str, int]:
    counters: dict[str, int] = defaultdict(int)
    for job in all_jobs:
        if job.status != GenerationJobStatus.PROCESSING:
            continue
        key = _project_key(job) if scope == 'project' else _client_key(job)
        counters[key] += 1
    return counters



def _build_rate_state(all_jobs: list[GenerationJob], *, now: datetime) -> dict[str, dict[str, int] | int]:
    window_start = now - timedelta(seconds=settings.generation_rate_limit_window_seconds)
    global_count = 0
    project_counts: dict[str, int] = defaultdict(int)
    client_counts: dict[str, int] = defaultdict(int)
    for job in all_jobs:
        started_at = getattr(job, 'started_at', None)
        if started_at is None or started_at < window_start:
            continue
        if job.status not in {GenerationJobStatus.PROCESSING, GenerationJobStatus.SUCCEEDED, GenerationJobStatus.FAILED}:
            continue
        global_count += 1
        project_counts[_project_key(job)] += 1
        client_counts[_client_key(job)] += 1
    return {
        'global': global_count,
        'project': project_counts,
        'client': client_counts,
    }



def _within_rate_limits(job: GenerationJob, *, rate_state: dict[str, dict[str, int] | int]) -> bool:
    project_counts = rate_state['project']
    client_counts = rate_state['client']
    assert isinstance(project_counts, dict)
    assert isinstance(client_counts, dict)
    if int(rate_state['global']) >= settings.generation_global_rate_limit_per_window:
        return False
    if project_counts[_project_key(job)] >= settings.generation_project_rate_limit_per_window:
        return False
    if client_counts[_client_key(job)] >= settings.generation_client_rate_limit_per_window:
        return False
    return True



def _consume_rate_limits(job: GenerationJob, *, rate_state: dict[str, dict[str, int] | int]) -> None:
    project_counts = rate_state['project']
    client_counts = rate_state['client']
    assert isinstance(project_counts, dict)
    assert isinstance(client_counts, dict)
    rate_state['global'] = int(rate_state['global']) + 1
    project_counts[_project_key(job)] += 1
    client_counts[_client_key(job)] += 1



def _assign_jobs_to_slots(jobs: list[GenerationJob], *, pool_size: int) -> list[list[GenerationJob]]:
    slots: list[list[GenerationJob]] = [[] for _ in range(pool_size)]
    project_slot_index: dict[str, int] = {}
    client_slot_usage: dict[str, set[int]] = defaultdict(set)
    for job in jobs:
        project_key = _project_key(job)
        client_key = _client_key(job)
        slot_index = project_slot_index.get(project_key)
        if slot_index is None:
            slot_index = _select_slot_for_job(slots, client_key=client_key, client_slot_usage=client_slot_usage)
            if slot_index is None:
                slot_index = min(range(pool_size), key=lambda idx: len(slots[idx]))
            project_slot_index[project_key] = slot_index
        slots[slot_index].append(job)
        client_slot_usage[client_key].add(slot_index)
    return slots



def _select_slot_for_job(
    slots: list[list[GenerationJob]],
    *,
    client_key: str,
    client_slot_usage: dict[str, set[int]],
) -> int | None:
    allowed_limit = max(1, settings.generation_client_concurrency_limit)
    allowed_slots = client_slot_usage[client_key]
    available_indexes = [
        index for index in range(len(slots)) if index in allowed_slots or len(allowed_slots) < allowed_limit
    ]
    if not available_indexes:
        return None
    return min(available_indexes, key=lambda idx: len(slots[idx]))



def _project_key(job: GenerationJob) -> str:
    return str(job.project_id) if job.project_id is not None else f'unscoped:{job.id}'



def _client_key(job: GenerationJob) -> str:
    if job.client_account_id is not None:
        return str(job.client_account_id)
    return f'project:{_project_key(job)}'
