from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class OperationMode(str, Enum):
    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"
    AUTO = "auto"


class PublishMode(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    AUTO = "auto"


class AgentRole(str, Enum):
    STRATEGIST = "strategist"
    RESEARCHER = "researcher"
    WRITER = "writer"
    EDITOR = "editor"
    FACT_CHECKER = "fact_checker"
    PUBLISHER = "publisher"


class ContentPlanPeriod(str, Enum):
    WEEK = "week"
    MONTH = "month"


class ContentTaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DRAFTED = "drafted"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class DraftStatus(str, Enum):
    CREATED = "created"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PublicationStatus(str, Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELED = "canceled"


class SubscriptionStatus(str, Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    SUSPENDED = "suspended"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class GenerationJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GenerationJobOperation(str, Enum):
    CREATE_DRAFT = "create_draft"
    REGENERATE_DRAFT = "regenerate_draft"
    REWRITE_DRAFT = "rewrite_draft"
    GENERATE_CONTENT_PLAN = "generate_content_plan"
