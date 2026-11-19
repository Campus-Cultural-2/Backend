from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ParticipantOut(BaseModel):
    user_id: int
    name: str
    last_name: str
    ra: str | None
    # Em eventos sem confirmacao, todos os inscritos contam como presentes.
    attended: bool
    checked_in_at: datetime | None


class ManualAttendanceIn(BaseModel):
    present: bool


class AttendanceCodeIn(BaseModel):
    code: str


class EventCodeOut(BaseModel):
    code: str
