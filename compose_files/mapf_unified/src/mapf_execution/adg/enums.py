from enum import Enum


class TaskState(Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    QUEUED = "queued"
