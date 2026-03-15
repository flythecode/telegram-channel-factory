from app.models.agent_profile import AgentProfile
from app.models.project import Project
from app.models.telegram_channel import TelegramChannel
from app.models.user import User
from app.models.workspace import Workspace
from app.utils.enums import AgentRole


def test_workspace_can_hold_multiple_channel_projects_with_isolated_agent_teams(fake_db):
    user = User(email="tenant@example.com", full_name="Tenant Owner", telegram_user_id="tenant-1")
    fake_db.add(user)
    fake_db.refresh(user)

    workspace = Workspace(
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name="Tenant Workspace",
        slug="tenant-workspace",
    )
    fake_db.add(workspace)
    fake_db.refresh(workspace)

    project_alpha = Project(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name="Alpha Channel Project",
        language="ru",
    )
    project_beta = Project(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        created_by_user_id=user.id,
        name="Beta Channel Project",
        language="ru",
    )
    fake_db.add(project_alpha)
    fake_db.add(project_beta)
    fake_db.refresh(project_alpha)
    fake_db.refresh(project_beta)

    channel_alpha = TelegramChannel(project_id=project_alpha.id, channel_title="Alpha Channel", channel_username="alpha")
    channel_beta = TelegramChannel(project_id=project_beta.id, channel_title="Beta Channel", channel_username="beta")
    fake_db.add(channel_alpha)
    fake_db.add(channel_beta)
    fake_db.refresh(channel_alpha)
    fake_db.refresh(channel_beta)

    alpha_agent = AgentProfile(
        project_id=project_alpha.id,
        channel_id=channel_alpha.id,
        role=AgentRole.STRATEGIST,
        name="alpha-strategist",
        model="stub",
    )
    beta_agent = AgentProfile(
        project_id=project_beta.id,
        channel_id=channel_beta.id,
        role=AgentRole.EDITOR,
        name="beta-editor",
        model="stub",
    )
    fake_db.add(alpha_agent)
    fake_db.add(beta_agent)
    fake_db.refresh(alpha_agent)
    fake_db.refresh(beta_agent)

    assert project_alpha.workspace_id == workspace.id
    assert project_beta.workspace_id == workspace.id
    assert channel_alpha.project_id == project_alpha.id
    assert channel_beta.project_id == project_beta.id
    assert alpha_agent.project_id == project_alpha.id
    assert beta_agent.project_id == project_beta.id
    assert alpha_agent.channel_id == channel_alpha.id
    assert beta_agent.channel_id == channel_beta.id
    assert alpha_agent.project_id != beta_agent.project_id
