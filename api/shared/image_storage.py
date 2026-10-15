from __future__ import annotations

import logging
from dataclasses import dataclass

import cloudinary.uploader
from cloudinary.exceptions import BadRequest as CloudinaryBadRequest
from cloudinary.exceptions import Error as CloudinaryError
from starlette.concurrency import run_in_threadpool

from api.shared.exceptions import BadRequestError, ErrorCode, ServiceUnavailableError
from database.config.settings import settings

EVENT_IMAGES_FOLDER = "campus_cultural/events"
PROFILE_PICTURES_FOLDER = "campus_cultural/profile_pictures"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredImage:
    # Link publico, usado pelo app e pelo site para mostrar a imagem.
    url: str
    # Identificador da imagem no Cloudinary, usado para apaga-la depois.
    public_id: str


class ImageStorage:
    """Guarda e apaga imagens no Cloudinary. O banco guarda so o link e o id."""

    async def upload(self, image: bytes, folder: str) -> StoredImage:
        if not image:
            raise BadRequestError("Image is empty", code=ErrorCode.INVALID_IMAGE)

        if not settings.is_cloudinary_configured:
            raise ServiceUnavailableError(
                "Image storage is not configured",
                code=ErrorCode.IMAGE_STORAGE_UNAVAILABLE,
            )

        try:
            # O SDK do Cloudinary e sincrono. Rodar em outra thread evita que
            # o upload trave as demais requisicoes enquanto espera a rede.
            result = await run_in_threadpool(
                cloudinary.uploader.upload,
                image,
                folder=folder,
                resource_type="image",
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
            )
        except CloudinaryBadRequest as exc:
            # O Cloudinary recusa arquivos que nao sao imagem.
            raise BadRequestError("Invalid image file", code=ErrorCode.INVALID_IMAGE) from exc
        except CloudinaryError as exc:
            raise ServiceUnavailableError(
                "Could not upload image",
                code=ErrorCode.IMAGE_STORAGE_UNAVAILABLE,
            ) from exc

        return StoredImage(url=result["secure_url"], public_id=result["public_id"])

    async def delete(self, public_id: str) -> None:
        """Apaga a imagem do Cloudinary.

        Quem chama ja salvou a mudanca no banco, entao uma falha aqui nao
        desfaz nada nem derruba a requisicao: a imagem fica sobrando no
        Cloudinary e um aviso com o public_id vai para o log.
        """
        if not settings.is_cloudinary_configured:
            logger.warning("Image %s was not deleted: Cloudinary is not configured", public_id)
            return

        try:
            result = await run_in_threadpool(
                cloudinary.uploader.destroy,
                public_id,
                resource_type="image",
                # Tira a imagem do cache da CDN, para o link parar de funcionar.
                invalidate=True,
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
            )
        except Exception:
            logger.warning("Could not delete image %s from Cloudinary", public_id, exc_info=True)
            return

        # "not found" quer dizer que a imagem ja nao existia: nada a fazer.
        if result.get("result") not in ("ok", "not found"):
            logger.warning("Cloudinary did not delete image %s: %s", public_id, result)
