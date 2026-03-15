from app.models.agent_profile import AgentProfile
from app.models.client_account import ClientAccount
from app.models.content_task import ContentTask
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.services.agent_service import apply_preset_to_project, ensure_default_presets
from app.services.orchestration import run_linear_orchestration
from app.utils.enums import AgentRole, SubscriptionStatus


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


def test_trial_plan_uses_single_pass_even_with_legacy_multi_agent_team(fake_db):
    user = User(email='trial-pipeline@example.com', telegram_user_id='trial-pipeline')
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(owner_user_id=user.id, created_by_user_id=user.id, name='Trial Pipeline WS', slug='trial-pipeline-ws')
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    account = ClientAccount(
        owner_user_id=user.id,
        workspace_id=workspace.id,
        name='Trial Pipeline Account',
        subscription_plan_code='trial',
        subscription_status=SubscriptionStatus.TRIAL,
    )
    fake_db.add(account)
    fake_db.refresh(account)

    project = Project(
        workspace_id=workspace.id,
        client_account_id=account.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name='Trial Pipeline Project',
        language='ru',
    )
    fake_db.add(project)
    fake_db.refresh(project)

    for index, role in enumerate(
        [AgentRole.STRATEGIST, AgentRole.RESEARCHER, AgentRole.WRITER, AgentRole.EDITOR, AgentRole.PUBLISHER],
        start=1,
    ):
        fake_db.add(
            AgentProfile(
                project_id=project.id,
                role=role,
                name=f'trial-{role.value}-{index}',
                display_name=f'Trial {role.value.title()}',
                model='stub',
                sort_order=index,
                priority=index * 10,
            )
        )

    task = ContentTask(project_id=project.id, title='Pipeline Task', brief='Brief')
    fake_db.add(task)
    fake_db.refresh(task)

    result = run_linear_orchestration(fake_db, task)

    assert result.execution_context.agent_team_runtime.generation_mode == 'single-pass'
    assert len(result.stages) == 1
    assert result.stages[0].role == 'publisher'
    assert result.final_agent_name == 'Trial Publisher'
