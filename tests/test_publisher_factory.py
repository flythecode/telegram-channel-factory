from app.services.publisher_factory import get_publisher
from app.services.stub_publisher import StubPublisher
from app.services.telegram_publisher import TelegramPublisher



def test_publisher_factory_returns_stub_by_default():
    publisher = get_publisher()
    assert isinstance(publisher, StubPublisher)



def test_telegram_publisher_interface_exists():
    publisher = TelegramPublisher()
    assert hasattr(publisher, 'publish')
    assert hasattr(publisher, 'fail')
