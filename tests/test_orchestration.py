from app.models.agent_profile import AgentProfile
from app.models.content_task import ContentTask
from app.models.project import Project
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
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


def test_run_linear_orchestration_builds_stage_chain(fake_db):
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

    result = run_linear_orchestration(fake_db, task)

    assert len(result.stages) == 2
    assert result.preset_code is None
    assert result.stages[0].role == 'strategist'
    assert result.stages[1].role == 'writer'
    assert result.final_agent_name == 'Writer'
    assert 'BTC Update' in result.final_text
    assert 'Prompt: Focus on concise delivery' in result.final_text
