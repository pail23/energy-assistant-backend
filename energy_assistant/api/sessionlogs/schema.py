"""Schemas for session logs api."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionLogEntrySchema(BaseModel):
    """API Response for reading a session log entry."""

    start: datetime
    end: datetime
    text: str
    device_id: uuid.UUID
    solar_consumed_energy: float
    consumed_energy: float

    model_config = ConfigDict(from_attributes=True)


class ReadAllSessionLogEntriesResponse(BaseModel):
    """API Response for reading session log entries."""

    entries: list[SessionLogEntrySchema]
