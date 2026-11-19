from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    event_id: int
    created_at: datetime
    # Quando a presenca foi confirmada; nulo se ainda nao foi.
    checked_in_at: datetime | None = None
    # Codigo (para virar QR code) que o professor le para confirmar a presenca.
    # So existe em eventos com confirmacao pelo professor.
    attendance_code: str | None = None
