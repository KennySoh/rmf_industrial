from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

"""Models for MAPF used across external requests and execution.
"""

# TODO Decouple model objects from web server or consolidate them in the same place.


class MapfSendTaskPostRequestTaskItem(BaseModel):
    task_id: Optional[str] = Field(None, json_schema_extra={"example": "7235686cd3"})
    robot_id: str = Field(None, json_schema_extra={"example": "agv_1"})
    start_location: str = Field(
        None, json_schema_extra={"example": "wp1", "pybullet_example": "2, 4"}
    )
    goal_location: str = Field(None, json_schema_extra={"example": "wp1"})


class GracefulPause(BaseModel):
    task_id: str = Field(None, json_schema_extra={"example": "7235686cd3"})


class ReplaceDestination(BaseModel):
    task_id: Optional[str] = Field(None, json_schema_extra={"example": "7235686cd3"})
    robot_id: str = Field(None, json_schema_extra={"example": "agv_1"})
    goal_location: str = Field(None, json_schema_extra={"example": "wp1"})
