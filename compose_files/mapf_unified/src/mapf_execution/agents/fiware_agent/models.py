from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PathItem(BaseModel):
    sequence_id: int
    node: str = Field(None, json_schema_extra={"example": "wp1"})
    released: bool


class McUpdateOrderPostRequestItem(BaseModel):
    robot_id: str
    task_id: str
    order_id: Optional[str]
    path: List[PathItem]
