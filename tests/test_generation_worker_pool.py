from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.services.generation_queue import enqueue_generation_job, list_generation_jobs
from app.services.generation_worker_pool import process_generation_worker_pool
from app.utils.enums import ContentTaskStatus, GenerationJobOperation, GenerationJobStatus, ProjectStatus, SubscriptionStatus


def _make_project_with_task(fake_db, name: str, *, client_account_id=None):
    project = Project(name=name, language='ru', status=ProjectStatus.ACTIVE, client_account_id=client_account_id)
    fake_db.add(project)
    fake_db.refresh(project)
    task = ContentTask(project_id=project.id, title=f'{name} task', status=ContentTaskStatus.PENDING)
    fake_db.add(task)
    fake_db.refresh(task)
    return project, task


def _make_client_account(fake_db, *, plan_code='trial', status=SubscriptionStatus.TRIAL):
    user = User(email=f'{plan_code}-{status.value}@example.com')
    fake_db.add(user)
    fake_db.refresh(user)
    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name=f'{plan_code} workspace', slug=f'{plan_code}-{status.value}')
    fake_db.add(workspace)
    fake_db.refresh(workspace)
    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name=f'{plan_code} account',
        billing_email=user.email,
        subscription_plan_code=plan_code,
        subscription_status=status,
    )
    fake_db.add(account)
    fake_db.refresh(account)
    return account


def test_generation_worker_pool_keeps_project_jobs_in_single_slot(fake_db):
    project_a, task_a1 = _make_project_with_task(fake_db, 'Pool Project A')
    _project_a, task_a2 = _make_project_with_task(fake_db, 'Pool Project A second')
    task_a2.project_id = project_a.id
    fake_db.add(task_a2)
    project_b, task_b = _make_project_with_task(fake_db, 'Pool Project B')

    enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project_a.id,
        content_task_id=task_a1.id,
        payload={'text': 'A1'},
    )
    enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project_a.id,
        content_task_id=task_a2.id,
        payload={'text': 'A2'},
    )
    enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project_b.id,
        content_task_id=task_b.id,
        payload={'text': 'B1'},
    )

    summary = process_generation_worker_pool(fake_db, pool_size=2)

    assert summary.processed == 3
    assert summary.failed == 0
    assert summary.projects_seen == 2
    slot_map = {slot.project_id: slot for slot in summary.slots}
    assert str(project_a.id) in slot_map
    assert len(slot_map[str(project_a.id)].job_ids) == 2
    assert len(summary.slots) == 2


def test_generation_worker_pool_respects_batch_limit(fake_db):
    project, task1 = _make_project_with_task(fake_db, 'Limited Project')
    _project, task2 = _make_project_with_task(fake_db, 'Limited Project second')
    task2.project_id = project.id
    fake_db.add(task2)

    job1 = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task1.id,
        payload={'text': 'L1'},
    )
    job2 = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task2.id,
        payload={'text': 'L2'},
    )

    summary = process_generation_worker_pool(fake_db, pool_size=1, batch_limit=1)

    assert summary.processed == 1
    assert job1.status == GenerationJobStatus.SUCCEEDED
    assert job2.status == GenerationJobStatus.QUEUED


def test_generation_job_priority_prefers_urgent_and_paid_workloads(fake_db):
    trial_account = _make_client_account(fake_db, plan_code='trial', status=SubscriptionStatus.TRIAL)
    premium_account = _make_client_account(fake_db, plan_code='premium', status=SubscriptionStatus.ACTIVE)
    trial_project, trial_task = _make_project_with_task(fake_db, 'Trial Project', client_account_id=trial_account.id)
    premium_project, premium_task = _make_project_with_task(fake_db, 'Premium Project', client_account_id=premium_account.id)

    trial_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=trial_project.id,
        content_task_id=trial_task.id,
        payload={'text': 'trial draft'},
    )
    premium_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=premium_project.id,
        content_task_id=premium_task.id,
        payload={'text': 'premium draft'},
    )
    urgent_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.REWRITE_DRAFT,
        project_id=trial_project.id,
        content_task_id=trial_task.id,
        payload={'rewrite_prompt': 'urgent fix', 'is_urgent': True},
    )

    ordered_jobs = list_generation_jobs(fake_db)

    assert [job.id for job in ordered_jobs[:3]] == [urgent_job.id, premium_job.id, trial_job.id]
    assert urgent_job.priority == 0
    assert premium_job.priority < trial_job.priority


def test_generation_worker_pool_assigns_high_priority_projects_first(fake_db):
    premium_account = _make_client_account(fake_db, plan_code='business', status=SubscriptionStatus.ACTIVE)
    trial_account = _make_client_account(fake_db, plan_code='trial', status=SubscriptionStatus.TRIAL)
    premium_project, premium_task = _make_project_with_task(fake_db, 'Priority Premium', client_account_id=premium_account.id)
    trial_project, trial_task = _make_project_with_task(fake_db, 'Priority Trial', client_account_id=trial_account.id)

    premium_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=premium_project.id,
        content_task_id=premium_task.id,
        payload={'text': 'premium first'},
    )
    trial_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.GENERATE_CONTENT_PLAN,
        project_id=trial_project.id,
        content_task_id=trial_task.id,
        payload={'text': 'trial later'},
    )

    summary = process_generation_worker_pool(fake_db, pool_size=1, batch_limit=1)

    assert summary.queued_seen == 2
    assert summary.processed == 1
    assert premium_job.status == GenerationJobStatus.SUCCEEDED
    assert trial_job.status == GenerationJobStatus.QUEUED
    assert summary.slots[0].project_id.split(',')[0] == str(premium_project.id)


def test_generation_worker_pool_respects_active_project_concurrency_limit(fake_db):
    project, task1 = _make_project_with_task(fake_db, 'Concurrency Project')
    _project, task2 = _make_project_with_task(fake_db, 'Concurrency Project second')
    task2.project_id = project.id
    fake_db.add(task2)

    processing_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task1.id,
        payload={'text': 'already running'},
    )
    processing_job.status = GenerationJobStatus.PROCESSING
    processing_job.started_at = datetime.now(timezone.utc)
    fake_db.add(processing_job)

    queued_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task2.id,
        payload={'text': 'should wait'},
    )

    summary = process_generation_worker_pool(fake_db, pool_size=2)

    assert summary.processed == 0
    assert queued_job.status == GenerationJobStatus.QUEUED



def test_generation_worker_pool_limits_client_parallel_slots(fake_db, monkeypatch):
    monkeypatch.setattr(settings, 'generation_client_concurrency_limit', 1)
    client_account = _make_client_account(fake_db, plan_code='premium', status=SubscriptionStatus.ACTIVE)
    project_a, task_a = _make_project_with_task(fake_db, 'Client Project A', client_account_id=client_account.id)
    project_b, task_b = _make_project_with_task(fake_db, 'Client Project B', client_account_id=client_account.id)

    job_a = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project_a.id,
        content_task_id=task_a.id,
        payload={'text': 'A'},
    )
    job_b = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project_b.id,
        content_task_id=task_b.id,
        payload={'text': 'B'},
    )

    summary = process_generation_worker_pool(fake_db, pool_size=4, batch_limit=2)

    assert summary.processed == 2
    assert job_a.status == GenerationJobStatus.SUCCEEDED
    assert job_b.status == GenerationJobStatus.SUCCEEDED
    assert len(summary.slots) == 1



def test_generation_worker_pool_applies_project_rate_limit(fake_db, monkeypatch):
    monkeypatch.setattr(settings, 'generation_rate_limit_window_seconds', 60)
    monkeypatch.setattr(settings, 'generation_project_rate_limit_per_window', 1)
    project, task1 = _make_project_with_task(fake_db, 'Rate Limited Project')
    _project, task2 = _make_project_with_task(fake_db, 'Rate Limited Project second')
    task2.project_id = project.id
    fake_db.add(task2)

    recent_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task1.id,
        payload={'text': 'recent'},
    )
    recent_job.status = GenerationJobStatus.SUCCEEDED
    recent_job.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    recent_job.finished_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    fake_db.add(recent_job)

    queued_job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task2.id,
        payload={'text': 'must wait'},
    )

    summary = process_generation_worker_pool(fake_db, pool_size=2)

    assert summary.processed == 0
    assert queued_job.status == GenerationJobStatus.QUEUED


@dataclass(slots=True)
class _FastProcessedResult:
    job: object


def test_generation_worker_pool_handles_large_multi_tenant_backlog(fake_db, monkeypatch):
    monkeypatch.setattr(settings, 'generation_client_concurrency_limit', 3)
    monkeypatch.setattr(settings, 'generation_project_concurrency_limit', 1)
    monkeypatch.setattr(settings, 'generation_global_rate_limit_per_window', 200)
    monkeypatch.setattr(settings, 'generation_client_rate_limit_per_window', 50)
    monkeypatch.setattr(settings, 'generation_project_rate_limit_per_window', 10)

    processed_order: list[tuple[str, str]] = []

    def _fast_process(db, job):
        job.status = GenerationJobStatus.SUCCEEDED
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        processed_order.append((str(job.client_account_id), str(job.project_id)))
        return _FastProcessedResult(job=job)

    monkeypatch.setattr('app.services.generation_worker_pool.process_claimed_generation_job', _fast_process)

    expected_jobs = 0
    client_ids: list[str] = []
    for client_index in range(12):
        account = _make_client_account(
            fake_db,
            plan_code='business' if client_index % 2 == 0 else 'trial',
            status=SubscriptionStatus.ACTIVE if client_index % 2 == 0 else SubscriptionStatus.TRIAL,
        )
        client_ids.append(str(account.id))
        for project_index in range(3):
            project, task = _make_project_with_task(
                fake_db,
                f'Load Client {client_index} Project {project_index}',
                client_account_id=account.id,
            )
            enqueue_generation_job(
                fake_db,
                operation=GenerationJobOperation.CREATE_DRAFT,
                project_id=project.id,
                content_task_id=task.id,
                payload={'text': f'{client_index}-{project_index}-a'},
            )
            extra_task = ContentTask(
                project_id=project.id,
                title=f'Load extra {client_index}-{project_index}',
                status=ContentTaskStatus.PENDING,
            )
            fake_db.add(extra_task)
            fake_db.refresh(extra_task)
            enqueue_generation_job(
                fake_db,
                operation=GenerationJobOperation.REWRITE_DRAFT,
                project_id=project.id,
                content_task_id=extra_task.id,
                payload={'rewrite_prompt': 'load rewrite'},
            )
            expected_jobs += 2

    summary = process_generation_worker_pool(fake_db, pool_size=36, batch_limit=expected_jobs)

    assert summary.queued_seen == expected_jobs == 72
    assert summary.processed == expected_jobs
    assert summary.failed == 0
    assert summary.projects_seen == 36
    assert summary.slots_used <= 36
    assert len(processed_order) == expected_jobs
    client_parallel_slots: dict[str, set[int]] = {}
    for slot in summary.slots:
        slot_clients = {client_id for client_id, project_id in processed_order if project_id in slot.project_id.split(',')}
        for client_id in slot_clients:
            client_parallel_slots.setdefault(client_id, set()).add(slot.slot_index)
    assert max(len(slot_indexes) for slot_indexes in client_parallel_slots.values()) <= 3


def test_generation_worker_pool_load_prefers_paid_projects_under_batch_pressure(fake_db, monkeypatch):
    monkeypatch.setattr(settings, 'generation_client_concurrency_limit', 1)

    def _fast_process(db, job):
        job.status = GenerationJobStatus.SUCCEEDED
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        return _FastProcessedResult(job=job)

    monkeypatch.setattr('app.services.generation_worker_pool.process_claimed_generation_job', _fast_process)

    premium_projects = []
    trial_projects = []
    for index in range(6):
        premium_account = _make_client_account(fake_db, plan_code='business', status=SubscriptionStatus.ACTIVE)
        trial_account = _make_client_account(fake_db, plan_code='trial', status=SubscriptionStatus.TRIAL)
        premium_project, premium_task = _make_project_with_task(fake_db, f'Premium Load {index}', client_account_id=premium_account.id)
        trial_project, trial_task = _make_project_with_task(fake_db, f'Trial Load {index}', client_account_id=trial_account.id)
        premium_projects.append(str(premium_project.id))
        trial_projects.append(str(trial_project.id))
        enqueue_generation_job(
            fake_db,
            operation=GenerationJobOperation.CREATE_DRAFT,
            project_id=premium_project.id,
            content_task_id=premium_task.id,
            payload={'text': f'premium-{index}'},
        )
        enqueue_generation_job(
            fake_db,
            operation=GenerationJobOperation.GENERATE_CONTENT_PLAN,
            project_id=trial_project.id,
            content_task_id=trial_task.id,
            payload={'text': f'trial-{index}'},
        )

    summary = process_generation_worker_pool(fake_db, pool_size=4, batch_limit=4)

    assert summary.processed == 4
    processed_projects = {project_id for slot in summary.slots for project_id in slot.project_id.split(',') if project_id}
    assert processed_projects.issubset(set(premium_projects))
    assert processed_projects.isdisjoint(set(trial_projects))



def test_generation_worker_pool_can_drain_sustained_backlog_across_multiple_batches(fake_db, monkeypatch):
    monkeypatch.setattr(settings, 'generation_client_concurrency_limit', 2)
    monkeypatch.setattr(settings, 'generation_project_concurrency_limit', 1)
    monkeypatch.setattr(settings, 'generation_global_rate_limit_per_window', 1000)
    monkeypatch.setattr(settings, 'generation_client_rate_limit_per_window', 1000)
    monkeypatch.setattr(settings, 'generation_project_rate_limit_per_window', 1000)

    processed_job_ids: list[str] = []

    def _fast_process(db, job):
        job.status = GenerationJobStatus.SUCCEEDED
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        processed_job_ids.append(str(job.id))
        return _FastProcessedResult(job=job)

    monkeypatch.setattr('app.services.generation_worker_pool.process_claimed_generation_job', _fast_process)

    total_jobs = 0
    for client_index in range(8):
        account = _make_client_account(
            fake_db,
            plan_code='business' if client_index < 4 else 'trial',
            status=SubscriptionStatus.ACTIVE if client_index < 4 else SubscriptionStatus.TRIAL,
        )
        for project_index in range(3):
            project, task = _make_project_with_task(
                fake_db,
                f'Sustained Worker Client {client_index} Project {project_index}',
                client_account_id=account.id,
            )
            enqueue_generation_job(
                fake_db,
                operation=GenerationJobOperation.CREATE_DRAFT,
                project_id=project.id,
                content_task_id=task.id,
                payload={'text': f'{client_index}-{project_index}-0'},
            )
            for extra_index in range(2):
                extra_task = ContentTask(
                    project_id=project.id,
                    title=f'Sustained extra {client_index}-{project_index}-{extra_index}',
                    status=ContentTaskStatus.PENDING,
                )
                fake_db.add(extra_task)
                fake_db.refresh(extra_task)
                enqueue_generation_job(
                    fake_db,
                    operation=GenerationJobOperation.REWRITE_DRAFT,
                    project_id=project.id,
                    content_task_id=extra_task.id,
                    payload={'rewrite_prompt': f'load-{extra_index}'},
                )
            total_jobs += 3

    pass_one = process_generation_worker_pool(fake_db, pool_size=6, batch_limit=18)
    pass_two = process_generation_worker_pool(fake_db, pool_size=6, batch_limit=18)
    pass_three = process_generation_worker_pool(fake_db, pool_size=6, batch_limit=18)
    pass_four = process_generation_worker_pool(fake_db, pool_size=6, batch_limit=18)

    assert pass_one.processed == 18
    assert pass_two.processed == 18
    assert pass_three.processed == 18
    assert pass_four.processed == 18
    assert len(processed_job_ids) == total_jobs == 72
    assert len(set(processed_job_ids)) == total_jobs
    assert sum(1 for job in list_generation_jobs(fake_db) if job.status == GenerationJobStatus.QUEUED) == 0



def test_generation_worker_pool_claims_jobs_before_processing(fake_db, monkeypatch):
    project, task = _make_project_with_task(fake_db, 'Claimed Project')
    job = enqueue_generation_job(
        fake_db,
        operation=GenerationJobOperation.CREATE_DRAFT,
        project_id=project.id,
        content_task_id=task.id,
        payload={'text': 'claim me'},
    )
    observed: list[tuple[GenerationJobStatus, bool]] = []

    def _assert_claimed_process(db, claimed_job):
        observed.append((claimed_job.status, bool(claimed_job.lease_token), claimed_job.started_at is not None))
        claimed_job.status = GenerationJobStatus.SUCCEEDED
        claimed_job.finished_at = datetime.now(timezone.utc)
        db.add(claimed_job)
        return _FastProcessedResult(job=claimed_job)

    monkeypatch.setattr('app.services.generation_worker_pool.process_claimed_generation_job', _assert_claimed_process)

    summary = process_generation_worker_pool(fake_db, pool_size=1, batch_limit=1)

    assert summary.processed == 1
    assert observed == [(GenerationJobStatus.PROCESSING, True, True)]
    assert job.status == GenerationJobStatus.SUCCEEDED



def test_generation_worker_pool_load_respects_global_rate_limit_saturation(fake_db, monkeypatch):
    monkeypatch.setattr(settings, 'generation_rate_limit_window_seconds', 3600)
    monkeypatch.setattr(settings, 'generation_global_rate_limit_per_window', 5)
    monkeypatch.setattr(settings, 'generation_client_rate_limit_per_window', 50)
    monkeypatch.setattr(settings, 'generation_project_rate_limit_per_window', 50)

    def _fast_process(db, job):
        job.status = GenerationJobStatus.SUCCEEDED
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        return _FastProcessedResult(job=job)

    monkeypatch.setattr('app.services.generation_worker_pool.process_claimed_generation_job', _fast_process)

    now = datetime.now(timezone.utc)
    for index in range(4):
        project, task = _make_project_with_task(fake_db, f'Rate Saturation Historical {index}')
        historical_job = enqueue_generation_job(
            fake_db,
            operation=GenerationJobOperation.CREATE_DRAFT,
            project_id=project.id,
            content_task_id=task.id,
            payload={'text': f'historical-{index}'},
        )
        historical_job.status = GenerationJobStatus.SUCCEEDED
        historical_job.started_at = now - timedelta(minutes=5)
        historical_job.finished_at = now - timedelta(minutes=5)
        fake_db.add(historical_job)

    queued_jobs = []
    for index in range(6):
        project, task = _make_project_with_task(fake_db, f'Rate Saturation Queued {index}')
        queued_jobs.append(
            enqueue_generation_job(
                fake_db,
                operation=GenerationJobOperation.CREATE_DRAFT,
                project_id=project.id,
                content_task_id=task.id,
                payload={'text': f'queued-{index}'},
            )
        )

    summary = process_generation_worker_pool(fake_db, pool_size=6, batch_limit=6)

    assert summary.processed == 1
    assert queued_jobs[0].status == GenerationJobStatus.SUCCEEDED
    assert sum(1 for job in queued_jobs if job.status == GenerationJobStatus.QUEUED) == 5
