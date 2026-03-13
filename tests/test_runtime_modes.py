import os


def test_test_env_forces_safe_stub_runtime():
    assert os.environ['RUNTIME_MODE'] == 'stub'
    assert os.environ['PUBLISHER_BACKEND'] == 'stub'
    assert os.environ['TELEGRAM_BOT_TOKEN'] == ''
