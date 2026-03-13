from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.models.publication import Publication


class PublisherInterface(ABC):
    @abstractmethod
    def publish(self, db: Session, publication_id) -> Publication:
        raise NotImplementedError

    @abstractmethod
    def fail(self, db: Session, publication_id, reason: str = "publisher failure") -> Publication:
        raise NotImplementedError
