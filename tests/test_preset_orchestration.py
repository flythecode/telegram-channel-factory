from app.models.content_task import ContentTask
from app.models.project import Project
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
from app.services.orchestration import run_linear_orchestration, _resolve_stage_model
from app.core.config import settings


def test_default_stage_model_aliases_resolve_to_runtime_default(fake_db, monkeypatch):
    monkeypatch.setattr(settings, 'llm_model_default', 'gpt-4.1-mini')
    project = Project(name='Alias Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)
    ensure_default_presets(fake_db)
    agents = apply_preset_to_project(fake_db, project.id, 'starter_3')

    resolved = [_resolve_stage_model(agent) for agent in agents]

    assert all(model == 'gpt-4.1-mini' for model in resolved)



def test_starter_3_preset_drives_three_stage_pipeline(fake_db):
    project = Project(name='Starter 3 Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)
    ensure_default_presets(fake_db)
    apply_preset_to_project(fake_db, project.id, 'starter_3')

    task = ContentTask(project_id=project.id, title='Starter Task', brief='Brief')
    fake_db.add(task)
    fake_db.refresh(task)

    result = run_linear_orchestration(fake_db, task)

    assert result.preset_code == 'starter_3'
    assert len(result.applied_agent_ids) == 3
    assert [stage.role for stage in result.stages] == ['strategist', 'researcher', 'writer']


def test_balanced_5_preset_drives_five_stage_pipeline(fake_db):
    project = Project(name='Balanced 5 Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)
    ensure_default_presets(fake_db)
    apply_preset_to_project(fake_db, project.id, 'balanced_5')

    task = ContentTask(project_id=project.id, title='Balanced Task', brief='Brief')
    fake_db.add(task)
    fake_db.refresh(task)

    result = run_linear_orchestration(fake_db, task)

    assert result.preset_code == 'balanced_5'
    assert [stage.role for stage in result.stages] == ['strategist', 'researcher', 'writer', 'editor', 'publisher']


def test_editorial_7_preset_drives_editorial_pipeline(fake_db):
    project = Project(name='Editorial 7 Project', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)
    ensure_default_presets(fake_db)
    apply_preset_to_project(fake_db, project.id, 'editorial_7')

    task = ContentTask(project_id=project.id, title='Editorial Task', brief='Brief')
    fake_db.add(task)
    fake_db.refresh(task)

    result = run_linear_orchestration(fake_db, task)

    assert result.preset_code == 'editorial_7'
    assert len(result.stages) == 7
    assert result.stages[0].role == 'strategist'
    assert result.stages[1].role == 'researcher'
    assert result.stages[2].role == 'writer'
    assert result.stages[3].role == 'editor'
    assert result.stages[4].role == 'fact_checker'
    assert result.stages[5].role == 'publisher'
    assert result.stages[6].role == 'editor'
