import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.telegram_channel import TelegramChannel  # noqa: E402
from app.models.agent_profile import AgentProfile  # noqa: E402
from app.utils.enums import AgentRole, PublishMode  # noqa: E402


if __name__ == "__main__":
    db = SessionLocal()
    try:
        project = Project(
            name="Demo crypto media factory",
            description="Demo project for local MVP checks",
            niche="crypto",
            language="ru",
            tone_of_voice="concise, analytical",
            goal="Generate and approve Telegram content",
        )
        db.add(project)
        db.flush()

        channel = TelegramChannel(
            project_id=project.id,
            channel_title="Demo Channel",
            channel_username="demo_channel",
            publish_mode=PublishMode.MANUAL,
        )
        strategist = AgentProfile(
            project_id=project.id,
            role=AgentRole.STRATEGIST,
            name="Strategy Agent",
            model="claude-sonnet-4-5",
        )
        writer = AgentProfile(
            project_id=project.id,
            role=AgentRole.WRITER,
            name="Writer Agent",
            model="claude-sonnet-4-5",
        )
        db.add_all([channel, strategist, writer])
        db.commit()
        print(f"Seeded demo project: {project.id}")
    finally:
        db.close()
