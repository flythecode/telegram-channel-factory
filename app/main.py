from app.api_app import api_app, healthcheck

# Backward-compatible ASGI entrypoint.
app = api_app

__all__ = ["app", "api_app", "healthcheck"]
