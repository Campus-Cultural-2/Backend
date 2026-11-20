from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.features.attendance.attendance_schemas import (
    AttendanceCodeIn,
    EventCodeOut,
    ManualAttendanceIn,
    ParticipantOut,
)
from api.features.attendance.attendance_service import AttendanceService
from api.features.user.user import User
from api.shared.dependencies import get_attendance_service, get_current_user

router = APIRouter(prefix="/events", tags=["attendance"])


@router.get("/{event_id}/participants", response_model=list[ParticipantOut])
async def list_participants(
    event_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> list[ParticipantOut]:
    participants = await service.list_participants(event_id, current_user)
    return [ParticipantOut.model_validate(p, from_attributes=True) for p in participants]


@router.get("/{event_id}/attendance/code", response_model=EventCodeOut)
async def get_event_code(
    event_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> EventCodeOut:
    return EventCodeOut(code=await service.get_event_code(event_id, current_user))


@router.put("/{event_id}/participants/{user_id}/attendance", response_model=ParticipantOut)
async def set_attendance(
    event_id: int,
    user_id: int,
    payload: ManualAttendanceIn,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> ParticipantOut:
    participant = await service.set_attendance(event_id, user_id, payload.present, current_user)
    return ParticipantOut.model_validate(participant, from_attributes=True)


@router.post("/{event_id}/attendance/scan", response_model=ParticipantOut)
async def scan_student_code(
    event_id: int,
    payload: AttendanceCodeIn,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> ParticipantOut:
    participant = await service.scan_student_code(event_id, payload.code, current_user)
    return ParticipantOut.model_validate(participant, from_attributes=True)


@router.post("/{event_id}/attendance/check-in", response_model=ParticipantOut)
async def check_in(
    event_id: int,
    payload: AttendanceCodeIn,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> ParticipantOut:
    participant = await service.check_in(event_id, payload.code, current_user)
    return ParticipantOut.model_validate(participant, from_attributes=True)
