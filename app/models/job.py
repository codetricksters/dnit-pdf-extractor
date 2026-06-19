import enum
from dataclasses import dataclass, field
from datetime import datetime


class FileStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FileResult:
    filename: str
    status: FileStatus = FileStatus.PENDING
    error: str | None = None
    result_data: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class Job:
    job_id: str
    files: dict[str, FileResult] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed: bool = False
