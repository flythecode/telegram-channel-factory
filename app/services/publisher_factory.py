from app.core.config import settings
from app.services.publisher_interface import PublisherInterface
from app.services.stub_publisher import stub_publisher
from app.services.telegram_publisher import TelegramPublisher



def get_publisher() -> PublisherInterface:
    if settings.publisher_backend == "telegram":
        return TelegramPublisher()
    return stub_publisher
