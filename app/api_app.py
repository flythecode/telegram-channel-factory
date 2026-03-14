import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.request_context import reset_request_context, set_request_context

logger = logging.getLogger(__name__)

api_app = FastAPI(title=settings.app_name, debug=settings.debug)
api_app.include_router(api_router, prefix=settings.api_v1_prefix)


@api_app.middleware('http')
async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get('x-request-id') or str(uuid4())
    telegram_user_id = request.headers.get('x-telegram-user-id')
    started_at = time.perf_counter()
    request_token, telegram_token = set_request_context(request_id=request_id, telegram_user_id=telegram_user_id)

    logger.info(
        'request started',
        extra={
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'telegram_user_id': telegram_user_id,
        },
    )

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            'request failed',
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'telegram_user_id': telegram_user_id,
                'duration_ms': duration_ms,
                'error': str(exc),
            },
        )
        reset_request_context(request_token, telegram_token)
        return JSONResponse(
            status_code=500,
            content={'detail': 'Internal Server Error', 'request_id': request_id},
            headers={'x-request-id': request_id},
        )

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers['x-request-id'] = request_id
    logger.info(
        'request completed',
        extra={
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'telegram_user_id': telegram_user_id,
            'status_code': response.status_code,
            'duration_ms': duration_ms,
        },
    )
    reset_request_context(request_token, telegram_token)
    return response


@api_app.get('/health')
def healthcheck():
    return {'status': 'ok', 'service': settings.app_name}
