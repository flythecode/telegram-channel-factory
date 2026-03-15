import logging

from app.services.generation_observability import provider_health_snapshot, reset_provider_health
from app.services.generation_queue import enqueue_generation_job, list_generation_jobs
from app.services.generation_service import build_generation_service
from app.utils.enums import GenerationJobOperation


class _Project:
    def __init__(self, project_id='project-1'):
        self.id = project_id
        self.client_account_id = None


class _Task:
    def __init__(self, project=None, task_id='task-1', title='Task title'):
        self.id = task_id
        self.project = project or _Project()
        self.project_id = self.project.id
        self.title = title


def test_generation_queue_emits_snapshot_and_enqueue_logs(fake_db, caplog):
    reset_provider_health()
    with caplog.at_level(logging.INFO):
        enqueue_generation_job(
            fake_db,
            operation=GenerationJobOperation.CREATE_DRAFT,
            payload={'text': 'seed'},
            project_id='project-1',
            content_task_id='task-1',
        )
        list_generation_jobs(fake_db)

    messages = [record.message for record in caplog.records]
    assert 'generation job enqueued' in messages
    assert 'generation queue snapshot' in messages
    enqueue_records = [record for record in caplog.records if record.message == 'generation job enqueued']
    assert enqueue_records
    assert enqueue_records[-1].queue_snapshot['jobs_total'] == 1
    assert enqueue_records[-1].queue_snapshot['status_counts']['queued'] == 1


def test_generation_service_logs_structured_completion_event(fake_db, monkeypatch, caplog):
    reset_provider_health()

    class _Result:
        provider = 'stub'
        model = 'stub-default'
        output_text = 'Generated text'
        finish_reason = 'stop'
        request_id = 'req-obs-1'
        prompt_tokens = 10
        completion_tokens = 20
        total_tokens = 30
        latency_ms = 12
        raw_error = None
        failover = None

    monkeypatch.setattr(
        'app.services.generation_service.generate_with_failover',
        lambda _payload: _Result(),
    )

    with caplog.at_level(logging.INFO):
        build_generation_service(fake_db).rewrite_draft(
            type('Draft', (), {'id': 'draft-1', 'text': 'old', 'created_by_agent': 'writer', 'content_task': _Task()})(),
            rewrite_prompt='Сделай короче',
        )

    completion_records = [record for record in caplog.records if record.message == 'generation completed']
    assert completion_records
    assert completion_records[-1].operation_type == 'rewrite_draft'
    assert completion_records[-1].request_id == 'req-obs-1'
    assert completion_records[-1].total_tokens == 30


def test_llm_provider_updates_provider_health_and_failover_logs(monkeypatch, caplog):
    from app.core.config import settings
    from app.services.llm_provider import LLMGenerationRequest, LLMProviderError, OpenAIAdapter, generate_with_failover

    reset_provider_health()
    monkeypatch.setattr(settings, 'llm_provider', 'openai')
    monkeypatch.setattr(settings, 'llm_model_default', 'gpt-4.1-mini')
    monkeypatch.setattr(settings, 'llm_failover_strategy', 'fallback-provider')
    monkeypatch.setattr(settings, 'llm_fallback_provider', 'stub')
    monkeypatch.setattr(settings, 'llm_fallback_model', 'stub-fallback')

    def primary_generate(self, payload):
        raise LLMProviderError('primary down', provider='openai', retryable=True)

    monkeypatch.setattr(OpenAIAdapter, 'generate', primary_generate)

    with caplog.at_level(logging.INFO):
        result = generate_with_failover(LLMGenerationRequest(system_prompt='system', user_prompt='hello'))

    assert result.failover is not None
    assert result.failover['outcome'] == 'fallback-provider-succeeded'
    health = provider_health_snapshot('stub')
    assert health['last_status'] == 'ok'
    assert health['last_failover_outcome'] == 'fallback-provider-succeeded'
    assert any(record.message == 'llm failover activated' for record in caplog.records)
