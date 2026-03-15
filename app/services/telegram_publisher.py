import json
import logging
from datetime import datetime, timezone
from urllib import error, request

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.publication import Publication
from app.services.crud import get_entity_or_404
from app.services.publish_errors import RetryablePublishError
from app.services.publications import sync_task_status_from_publication
from app.services.publisher_interface import PublisherInterface
from app.utils.enums import PublicationStatus

logger = logging.getLogger(__name__)


class TelegramPublisher(PublisherInterface):
    def _resolve_chat_id(self, publication: Publication) -> str:
        channel = publication.telegram_channel
        if channel.channel_id:
            return channel.channel_id
        if channel.channel_username:
            username = channel.channel_username
            return username if username.startswith('@') else f'@{username}'
        raise ValueError('Telegram channel must have channel_id or channel_username')

    def _build_text(self, publication: Publication) -> str:
        return publication.draft.text

    def _resolve_media_urls(self, publication: Publication) -> list[str]:
        metadata = publication.generation_metadata or {}
        media = metadata.get('media')
        if isinstance(media, list):
            urls = [
                item.get('url')
                for item in media
                if isinstance(item, dict)
                and item.get('type') in {None, 'image', 'photo'}
                and isinstance(item.get('url'), str)
                and item.get('url').strip()
            ]
            if urls:
                return urls

        image_urls = metadata.get('image_urls')
        if isinstance(image_urls, list):
            return [item for item in image_urls if isinstance(item, str) and item.strip()]
        return []

    def _telegram_request(self, method: str, payload: dict):
        req = request.Request(
            url=f'https://api.telegram.org/bot{settings.telegram_bot_token}/{method}',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with request.urlopen(req, timeout=settings.telegram_request_timeout_seconds) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def _extract_retry_after(self, payload: dict | None) -> float | None:
        if not isinstance(payload, dict):
            return None
        parameters = payload.get('parameters')
        if not isinstance(parameters, dict):
            return None
        retry_after = parameters.get('retry_after')
        if retry_after is None:
            return None
        try:
            return float(retry_after)
        except (TypeError, ValueError):
            return None

    def _raise_retryable(self, reason: str, retry_after_seconds: float | None = None):
        raise RetryablePublishError(reason, retry_after_seconds=retry_after_seconds)

    def _mark_sent(self, db: Session, publication: Publication, message_id) -> Publication:
        publication.status = PublicationStatus.SENT
        publication.published_at = datetime.now(timezone.utc)
        publication.external_message_id = str(message_id) if message_id is not None else None
        publication.error_message = None

        task = publication.draft.content_task
        sync_task_status_from_publication(task, publication.status)

        db.add(publication)
        db.add(task)
        db.commit()
        db.refresh(publication)
        logger.info(
            "telegram publication sent",
            extra={
                "publication_id": str(publication.id),
                "message_id": publication.external_message_id,
                "task_id": str(task.id),
                "task_status": task.status.value,
            },
        )
        return publication

    def publish(self, db: Session, publication_id) -> Publication:
        publication = get_entity_or_404(db, Publication, publication_id, 'Publication not found')

        if not settings.telegram_bot_token:
            return self.fail(db, publication_id, 'TELEGRAM_BOT_TOKEN is not configured')

        try:
            chat_id = self._resolve_chat_id(publication)
        except ValueError as exc:
            return self.fail(db, publication_id, str(exc))

        text = self._build_text(publication)
        media_urls = self._resolve_media_urls(publication)
        logger.info(
            "telegram publish attempt",
            extra={
                "publication_id": str(publication.id),
                "chat_id": chat_id,
                "text_length": len(text),
                "media_count": len(media_urls),
            },
        )

        if media_urls:
            method = 'sendMediaGroup' if len(media_urls) > 1 else 'sendPhoto'
            if len(media_urls) > 1:
                payload = {
                    'chat_id': chat_id,
                    'media': [
                        {
                            'type': 'photo',
                            'media': url,
                            **({'caption': text} if index == 0 else {}),
                        }
                        for index, url in enumerate(media_urls)
                    ],
                }
            else:
                payload = {
                    'chat_id': chat_id,
                    'photo': media_urls[0],
                    'caption': text,
                }
        else:
            method = 'sendMessage'
            payload = {
                'chat_id': chat_id,
                'text': text,
                'disable_web_page_preview': True,
            }

        try:
            body = self._telegram_request(method, payload)
        except error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='ignore')
            parsed_detail = None
            try:
                parsed_detail = json.loads(detail) if detail else None
            except json.JSONDecodeError:
                parsed_detail = None
            reason = f'Telegram HTTP {exc.code}: {detail}'
            if exc.code == 429 or 500 <= exc.code < 600:
                self._raise_retryable(reason, retry_after_seconds=self._extract_retry_after(parsed_detail))
            return self.fail(db, publication_id, reason)
        except error.URLError as exc:
            self._raise_retryable(f'Telegram network error: {exc.reason}')
        except Exception as exc:
            self._raise_retryable(f'Telegram unexpected error: {exc}')

        if not body.get('ok'):
            reason = body.get('description', 'Telegram publish failed')
            retry_after_seconds = self._extract_retry_after(body)
            error_code = body.get('error_code')
            if error_code == 429 or retry_after_seconds is not None:
                self._raise_retryable(reason, retry_after_seconds=retry_after_seconds)
            return self.fail(db, publication_id, reason)

        result = body.get('result', {})
        if isinstance(result, list):
            message_id = result[0].get('message_id') if result and isinstance(result[0], dict) else None
        else:
            message_id = result.get('message_id')
        return self._mark_sent(db, publication, message_id)

    def fail(self, db: Session, publication_id, reason: str = 'telegram publish failure') -> Publication:
        publication = get_entity_or_404(db, Publication, publication_id, 'Publication not found')
        publication.status = PublicationStatus.FAILED
        publication.error_message = reason

        task = publication.draft.content_task
        sync_task_status_from_publication(task, publication.status)

        db.add(publication)
        db.add(task)
        db.commit()
        db.refresh(publication)
        logger.warning(
            "telegram publication failed",
            extra={
                "publication_id": str(publication.id),
                "task_id": str(task.id),
                "reason": reason,
            },
        )
        return publication
