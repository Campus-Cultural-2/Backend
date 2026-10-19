import base64
import binascii

from api.features.event.event import Event, HoursGroup
from api.features.event.event_repository import EventRepository
from api.features.event.event_schemas import EventCreateIn, EventUpdateIn
from api.features.user.user import User
from api.shared.exceptions import BadRequestError, ErrorCode, ResourceNotFoundError
from api.shared.image_storage import EVENT_IMAGES_FOLDER, ImageStorage, StoredImage


class EventService:
    def __init__(self, repository: EventRepository, image_storage: ImageStorage) -> None:
        self.repository = repository
        self.image_storage = image_storage

    async def create(self, payload: EventCreateIn, user: User) -> Event:
        event_data = payload.model_dump(exclude={"image"})
        _ensure_valid_certificate_info(
            payload.has_certificate, payload.workload_hours, payload.hours_group
        )

        # vínculo com usuário
        event_data["user_id"] = user.id

        event = Event(**event_data)
        _set_image(event, await self._upload_image(payload.image))

        return await self.repository.create(event)

    async def list_all(self) -> list[Event]:
        return await self.repository.list_all()

    async def get_by_id(self, event_id: int) -> Event:
        event = await self.repository.get_by_id(event_id)
        if event is None:
            raise ResourceNotFoundError(
                f"Event {event_id} not found",
                code=ErrorCode.EVENT_NOT_FOUND,
                details={"event_id": event_id},
            )
        return event

    async def list_by_user_id(self, user_id: int) -> list[Event]:
        return await self.repository.get_by_user_id(user_id)

    async def update(self, event_id: int, payload: EventUpdateIn, current_user: User) -> Event:
        event = await self.repository.get_by_id(event_id)

        if not event:
            raise ResourceNotFoundError(
                f"Event {event_id} not found",
                code=ErrorCode.EVENT_NOT_FOUND,
                details={"event_id": event_id},
            )

        if event.user_id != current_user.id:
            raise ResourceNotFoundError(
                "Event not found",
                code=ErrorCode.EVENT_NOT_FOUND,
            )

        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("has_certificate") is False:
            # Ao tirar o certificado, a carga horaria e o grupo deixam de valer.
            update_data.setdefault("workload_hours", None)
            update_data.setdefault("hours_group", None)
        _ensure_valid_certificate_info(
            update_data.get("has_certificate", event.has_certificate),
            update_data.get("workload_hours", event.workload_hours),
            update_data.get("hours_group", event.hours_group),
        )

        # Sem o campo image no payload, a imagem atual continua como esta.
        # Com image nulo, o evento fica sem imagem.
        replaces_image = "image" in update_data
        old_public_id = event.image_public_id
        if replaces_image:
            _set_image(event, await self._upload_image(update_data.pop("image")))

        for field, value in update_data.items():
            setattr(event, field, value)
        event = await self.repository.update(event)

        # So depois de salvar: a imagem antiga nao e mais usada por ninguem.
        if replaces_image and old_public_id:
            await self.image_storage.delete(old_public_id)
        return event

    async def delete(self, event_id: int, user: User) -> None:
        event = await self.get_by_id(event_id)

        #  proteção: só dono pode deletar
        if event.user_id != user.id:
            raise ResourceNotFoundError(
                "Event not found",
                code=ErrorCode.EVENT_NOT_FOUND,
            )

        image_public_id = event.image_public_id
        await self.repository.delete(event)

        # So depois de excluir o evento: a imagem dele nao e mais usada.
        if image_public_id:
            await self.image_storage.delete(image_public_id)

    async def _upload_image(self, image: str | None) -> StoredImage | None:
        if not image:
            return None
        return await self.image_storage.upload(_decode_base64_image(image), EVENT_IMAGES_FOLDER)


def _ensure_valid_certificate_info(
    has_certificate: bool | None,
    workload_hours: int | None,
    hours_group: HoursGroup | None,
) -> None:
    if has_certificate is None:
        raise BadRequestError(
            "has_certificate cannot be null",
            code=ErrorCode.INVALID_CERTIFICATE_INFO,
        )
    if has_certificate and (workload_hours is None or hours_group is None):
        raise BadRequestError(
            "Events with certificate must have workload_hours and hours_group",
            code=ErrorCode.INVALID_CERTIFICATE_INFO,
        )
    if not has_certificate and (workload_hours is not None or hours_group is not None):
        raise BadRequestError(
            "Events without certificate cannot have workload_hours or hours_group",
            code=ErrorCode.INVALID_CERTIFICATE_INFO,
        )


def _set_image(event: Event, image: StoredImage | None) -> None:
    event.image_url = image.url if image else None
    event.image_public_id = image.public_id if image else None


def _decode_base64_image(image: str) -> bytes:
    # O app manda so o base64, mas aceitamos tambem data URI
    # ("data:image/png;base64,...").
    _, separator, data = image.partition("base64,")
    encoded = data if separator else image
    try:
        # Remove quebras de linha que alguns celulares colocam no base64.
        return base64.b64decode("".join(encoded.split()), validate=True)
    except binascii.Error as exc:
        raise BadRequestError(
            "Image must be a base64 encoded file",
            code=ErrorCode.INVALID_IMAGE,
        ) from exc
