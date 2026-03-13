from app.models.content_task import ContentTask
from app.models.project import Project
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
from app.services.orchestration import run_linear_orchestration


def test_pipeline_is_reproducible_for_same_configuration(fake_db):
    project = Project(name='Reproducible Pipeline', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)
    ensure_default_presets(fake_db)
    apply_preset_to_project(fake_db, project.id, 'balanced_5')

    task = ContentTask(project_id=project.id, title='Pipeline Task', brief='Brief')
    fake_db.add(task)
    fake_db.refresh(task)

    result_one = run_linear_orchestration(fake_db, task)
    result_two = run_linear_orchestration(fake_db, task)

    assert result_one.preset_code == result_two.preset_code == 'balanced_5'
    assert result_one.applied_agent_ids == result_two.applied_agent_ids
    assert [stage.role for stage in result_one.stages] == [stage.role for stage in result_two.stages]
    assert result_one.final_text == result_two.final_text


def test_pipeline_changes_when_agent_is_disabled(fake_db):
    project = Project(name='Disable Pipeline Agent', language='ru')
    fake_db.add(project)
    fake_db.refresh(project)
    ensure_default_presets(fake_db)
    agents = apply_preset_to_project(fake_db, project.id, 'balanced_5')
    writer = next(agent for agent in agents if agent.role.value == 'writer')

    task = ContentTask(project_id=project.id, title='Pipeline Task', brief='Brief')
    fake_db.add(task)
    fake_db.refresh(task)

    before = run_linear_orchestration(fake_db, task)
    writer.is_enabled = False
    fake_db.add(writer)
    fake_db.refresh(writer)
    after = run_linear_orchestration(fake_db, task)

    assert len(before.stages) == 5
    assert len(after.stages) == 4
    assert 'writer' in [stage.role for stage in before.stages]
    assert 'writer' not in [stage.role for stage in after.stages]
