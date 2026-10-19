from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from api.features.event.event import HoursGroup


class EventBaseSchema(BaseModel):
    name: str
    event_datetime: datetime
    event_location: str
    description: str
    has_certificate: bool = False
    # Carga horaria e grupo de horas so existem quando o evento tem certificado.
    workload_hours: int | None = Field(default=None, ge=1)
    hours_group: HoursGroup | None = None


class EventCreateIn(EventBaseSchema):
    # Conteudo da imagem em base64 (tambem aceita data URI). O backend envia
    # o arquivo para o Cloudinary e guarda so o link.
    image: str | None = None


class EventOutSchema(EventBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    # Link da imagem no Cloudinary. No banco a coluna se chama image_url; na
    # API o campo continua sendo image, que e o nome que o app ja usa.
    image: str | None = Field(default=None, validation_alias=AliasChoices("image_url", "image"))


class EventCreateOut(EventOutSchema):
    pass


class EventReadOut(EventOutSchema):
    pass


class EventUpdateIn(BaseModel):
    image: str | None = None
    event_datetime: datetime | None = None
    name: str | None = None
    description: str | None = None
    event_location: str | None = None
    has_certificate: bool | None = None
    workload_hours: int | None = Field(default=None, ge=1)
    hours_group: HoursGroup | None = None


class EventUpdateOut(EventOutSchema):
    pass
