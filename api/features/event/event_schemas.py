from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class EventBaseSchema(BaseModel):
    name: str
    event_datetime: datetime
    event_location: str
    description: str
    # Sem limite quando nulo.
    max_participants: int | None = Field(default=None, ge=1)


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
    subscribers_count: int
    # Nulo quando o evento nao tem limite de participantes.
    available_spots: int | None
    is_full: bool


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
    # Com max_participants nulo, o evento fica sem limite.
    max_participants: int | None = Field(default=None, ge=1)


class EventUpdateOut(EventOutSchema):
    pass
