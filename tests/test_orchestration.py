from app.models.agent_profile import AgentProfile
from app.models.content_task import ContentTask
from app.models.project import Project
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
from app.services.llm_provider import LLMGenerationResult
from app.services.orchestration import get_active_agents_for_task, run_linear_orchestration
from app.utils.enums import AgentRole


def test_get_active_agents_for_task_orders_enabled_agents(fake_db):
    project = Project(name='Orchestration Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.WRITER,
            name='writer-2',
            model='writer',
            sort_order=20,
            priority=20,
        )
    )
    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.STRATEGIST,
            name='strategist-1',
            model='strategist',
            sort_order=10,
            priority=10,
        )
    )
    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.EDITOR,
            name='editor-disabled',
            model='editor',
            sort_order=30,
            priority=30,
            is_enabled=False,
        )
    )

    task = ContentTask(project_id=project.id, title='Test orchestration')
    agents = get_active_agents_for_task(fake_db, task)

    assert [agent.name for agent in agents] == ['strategist-1', 'writer-2']


def test_run_linear_orchestration_builds_stage_chain(fake_db, monkeypatch):
    project = Project(name='Linear Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.STRATEGIST,
            name='strategist-1',
            display_name='Strategist',
            model='strategist',
            sort_order=10,
            priority=10,
        )
    )
    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.WRITER,
            name='writer-1',
            display_name='Writer',
            model='writer',
            sort_order=20,
            priority=20,
            custom_prompt='Focus on concise delivery',
        )
    )

    task = ContentTask(project_id=project.id, title='BTC Update', topic='Bitcoin', brief='Quick market brief')
    fake_db.add(task)
    fake_db.refresh(task)

    class StubAdapter:
        def generate(self, payload):
            assert 'tenant-isolated Telegram content pipeline' in payload.system_prompt
            assert 'BTC Update' in payload.user_prompt
            return LLMGenerationResult(
                provider='openai',
                model='gpt-4.1-mini',
                output_text='Готовый пост про BTC.',
                finish_reason='stop',
                request_id='req-1',
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                latency_ms=55,
                raw_error=None,
            )

    monkeypatch.setattr('app.services.orchestration.get_llm_adapter', lambda: StubAdapter())

    result = run_linear_orchestration(fake_db, task)

    assert len(result.stages) == 2
    assert result.preset_code is None
    assert result.stages[0].role == 'strategist'
    assert result.stages[1].role == 'writer'
    assert result.final_agent_name == 'Writer'
    assert result.final_text == 'Готовый пост про BTC.'
    assert result.generation.provider == 'openai'
    assert result.generation.total_tokens == 60


def test_run_linear_orchestration_executes_each_stage_as_separate_generation(fake_db, monkeypatch):
    project = Project(name='Stage Calls Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)

    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.STRATEGIST,
            name='strategist-1',
            display_name='Strategist',
            model='stage-strategist',
            sort_order=10,
            priority=10,
        )
    )
    fake_db.add(
        AgentProfile(
            project_id=project.id,
            role=AgentRole.WRITER,
            name='writer-1',
            display_name='Writer',
            model='stage-writer',
            sort_order=20,
            priority=20,
        )
    )

    task = ContentTask(project_id=project.id, title='ETH Update', brief='Daily market summary')
    fake_db.add(task)
    fake_db.refresh(task)

    calls = []

    class StubAdapter:
        def generate(self, payload):
            calls.append(payload)
            role = 'writer' if 'writer stage' in payload.system_prompt else 'strategist'
            return LLMGenerationResult(
                provider='openai',
                model=payload.model or 'gpt-4.1-mini',
                output_text=f'{role.upper()} OUTPUT',
                finish_reason='stop',
                request_id=f'req-{len(calls)}',
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                latency_ms=50,
                raw_error=None,
            )

    monkeypatch.setattr('app.services.orchestration.get_llm_adapter', lambda: StubAdapter())

    result = run_linear_orchestration(fake_db, task)

    assert len(calls) == 2
    assert calls[0].model == 'stage-strategist'
    assert calls[1].model == 'stage-writer'
    assert 'Previous stage outputs:' in calls[1].user_prompt
    assert result.final_text == 'WRITER OUTPUT'
    assert result.stages[0].content == 'STRATEGIST OUTPUT'
    assert result.stages[1].content == 'WRITER OUTPUT'
    assert result.generation.total_tokens == 60
